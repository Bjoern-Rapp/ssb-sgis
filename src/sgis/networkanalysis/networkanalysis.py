"""Contains the NetworkAnalysis class.

The class has five methods: od_cost_matrix, get_route, get_k_routes,
get_route_frequencies and service_area.
"""


from copy import copy, deepcopy
from datetime import datetime
from time import perf_counter

import igraph
import numpy as np
import pandas as pd
from geopandas import GeoDataFrame
from igraph import Graph
from pandas import DataFrame

from ..geopandas_tools.general import _push_geom_col
from ..geopandas_tools.line_operations import split_lines_by_nearest_point
from ._get_route import _get_k_routes, _get_route, _get_route_frequencies
from ._od_cost_matrix import _od_cost_matrix
from ._points import Destinations, Origins
from ._service_area import _service_area
from .directednetwork import DirectedNetwork
from .network import Network
from .networkanalysisrules import NetworkAnalysisRules


class NetworkAnalysis:
    """Class for doing network analysis.

    The class takes a (Directed)Network and rules for the analyses
    (NetworkAnalysisRules), and holds methods that calculate travel times/costs,
    route geometries or travel frequencies.

    The analysis methods take a GeoDataFrame of origin points and a GeoDataFrame of
    destination points. The exception is the service_area methods, which take only
    origins. The travel cost or route between each OD (origin-destination) pair is
    calculated and returned in a (Geo)DataFrame with the columns 'origin',
    'destination' and the cost between the OD pairs. The route methods also return a
    geometry column.

    The methods use the index of the origins and destinations as values in the
    resulting DataFrames. To use a column instead, use the pandas set_index method
    inside the method call.

    The 'get_route_frequencies' method is a bit different. It returns the individual
    line segments that were visited with a column for how many times the segments
    were used.

    Also, the service area methods do not do calculations for OD pairs, but from either
    origins to all roads or all roads to destinations.

    Args:
        network: either the base Network class or a subclass, chiefly the
            DirectedNetwork class. The network can be customized beforehand, or
            accessed through the 'network' attribute of this class.
        rules: NetworkAnalysisRules class instance.
        log: If True (default), a DataFrame with information about each
            analysis run will be stored in the 'log' attribute.
        detailed_log: If True (default), the log DataFrame will include columns for
            all arguments held by the NetworkAnalysisRules class and the analysis
            method used. Will also include standard deviation, 25th, 50th and 75th
            percentile of the weight column in the results.

    Attributes:
        network: The Network instance.
        rules: The NetworkAnalysisRules instance.
        log: A DataFrame with information about each analysis run.

    See also
    --------
    DirectedNetwork : For customising and optimising line data before directed network
        analysis.

    Network : For customising and optimising line data before undirected network
        analysis.

    Examples
    --------
    Read example data.

    >>> import sgis as sg
    >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
    >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_eidskog.parquet")

    Creating a NetworkAnalysis class instance.

    >>> nw = (
    ...     sg.DirectedNetwork(roads)
    ...     .remove_isolated()
    ...     .make_directed_network(
    ...         direction_col="oneway",
    ...         direction_vals_bft=("B", "FT", "TF"),
    ...         minute_cols=("drivetime_fw", "drivetime_bw"),
    ...     )
    ... )
    >>> rules = sg.NetworkAnalysisRules(weight="minutes")
    >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)
    >>> nwa
    NetworkAnalysis(
        network=DirectedNetwork(6364 km, percent_bidirectional=87),
        rules=NetworkAnalysisRules(weight='minutes', search_tolerance=250, search_factor=10, split_lines=False, ...),
        log=True, detailed_log=True,
    )

    od_cost_matrix: fast many-to-many travel time/distance calculation.

    >>> od = nwa.od_cost_matrix(points, points)
    >>> od
            origin  destination    minutes
    0            0            0   0.000000
    1            0            1  13.039830
    2            0            2  10.902453
    3            0            3   8.297021
    4            0            4  14.742294
    ...        ...          ...        ...
    999995     999          995  11.038673
    999996     999          996  17.820664
    999997     999          997  10.288465
    999998     999          998  14.798257
    999999     999          999   0.000000
    [1000000 rows x 3 columns]

    get_route: get the geometry of the routes.

    >>> routes = nwa.get_route(points.sample(10), points.sample(10))
    >>> routes
        origin  destination    minutes                                           geometry
    0      112          501  20.016625  MULTILINESTRING Z ((256346.680 6651343.586 78....
    1      112            9  14.570397  MULTILINESTRING Z ((265186.200 6644291.300 145...
    2      112           88  14.976093  MULTILINESTRING Z ((265186.200 6644291.300 145...
    3      112          874  11.886933  MULTILINESTRING Z ((263069.585 6648646.891 5.1...
    4      112          939  10.308372  MULTILINESTRING Z ((264112.512 6640728.679 79....
    ..     ...          ...        ...                                                ...
    95     606            2  11.325834  MULTILINESTRING Z ((270054.367 6653367.774 144...
    96     606          511  15.045134  MULTILINESTRING Z ((258569.800 6652168.600 57....
    97     606          901  16.998595  MULTILINESTRING Z ((265040.505 6641218.021 100...
    98     606          766  10.094371  MULTILINESTRING Z ((265639.400 6649020.000 85....
    99     606          320   7.317098  MULTILINESTRING Z ((262711.480 6648807.500 3.8...
    [100 rows x 4 columns]

    get_route_frequencies: get the number of times each line segment was used.

    >>> frequencies = nwa.get_route_frequencies(points.sample(25), points.sample(25))
    >>> frequencies[[["source", "target", "frequency", "geometry"]]
           source target  frequency                                           geometry
    160188  77264  79112        1.0  LINESTRING Z (268641.225 6651871.624 111.355, ...
    138956  30221  45403        1.0  LINESTRING Z (273091.100 6652396.000 170.471, ...
    138958  30224  30221        1.0  LINESTRING Z (273117.500 6652391.500 169.771, ...
    138960  16513  30224        1.0  LINESTRING Z (273176.813 6652379.896 169.414, ...
    138962  40610  16513        1.0  LINESTRING Z (273207.300 6652372.100 168.871, ...
    ...       ...    ...        ...                                                ...
    151464  73800  73801      108.0  LINESTRING Z (265362.800 6647137.100 131.660, ...
    151465  73801  73802      108.0  LINESTRING Z (265368.600 6647142.900 131.660, ...
    151466  73802  73632      108.0  LINESTRING Z (265371.400 6647147.900 131.660, ...
    151463  73799  73800      129.0  LINESTRING Z (265359.600 6647135.400 131.660, ...
    152170  74418  74246      135.0  LINESTRING Z (264579.835 6651954.573 113.209, ...

    [8915 rows x 4 columns]

    service_area: get the area that can be reached within one or more breaks.

    >>> service_areas = nwa.service_area(
    ...         points.iloc[:3],
    ...         breaks=[5, 10, 15],
    ...     )
    >>> service_areas
       origin  minutes                                           geometry
    0       0        5  MULTILINESTRING Z ((265378.000 6650581.600 85....
    1       0       10  MULTILINESTRING Z ((264348.673 6648271.134 17....
    2       0       15  MULTILINESTRING Z ((263110.060 6658296.870 154...
    3       1        5  MULTILINESTRING Z ((273330.930 6653248.870 208...
    4       1       10  MULTILINESTRING Z ((266909.769 6651075.250 114...
    5       1       15  MULTILINESTRING Z ((264348.673 6648271.134 17....
    6       2        5  MULTILINESTRING Z ((269143.130 6652434.060 127...
    7       2       10  MULTILINESTRING Z ((266909.769 6651075.250 114...
    8       2       15  MULTILINESTRING Z ((264348.673 6648271.134 17....

    Check the log.

    >>> nwa.log
                  endtime  minutes_elapsed                 method  origins_count  destinations_count  percent_missing  cost_mean  isolated_removed  ...   cost_p25 cost_median   cost_p75  cost_std  lines rowwise     breaks  dissolve
    0 2023-03-29 15:19:51              0.5         od_cost_matrix           1000              1000.0           0.9966  15.270462              True  ...  10.565738   14.772737  19.337235  6.654981  False   False        NaN       NaN
    1 2023-03-29 15:20:21              0.5              get_route             10                10.0           0.0000  15.001443              True  ...  10.093613   14.641413  19.725085  6.869095    NaN   False        NaN       NaN
    2 2023-03-29 15:20:40              0.3  get_route_frequencies             25                25.0           0.0000   0.067199              True  ...   0.013309    0.038496   0.085692  0.087247    NaN     NaN        NaN       NaN
    3 2023-03-29 15:20:50              0.2           service_area              3                 NaN           0.0000  10.000000              True  ...   5.000000   10.000000  15.000000  4.330127    NaN     NaN  5, 10, 15      True
    [4 rows x 23 columns]

    """

    def __init__(
        self,
        network: Network | DirectedNetwork,
        rules: NetworkAnalysisRules,
        log: bool = True,
        detailed_log: bool = True,
    ):
        self.network = network
        self.rules = rules
        self._log = log
        self.detailed_log = detailed_log

        if not isinstance(rules, NetworkAnalysisRules):
            raise TypeError(
                f"'rules' should be of type NetworkAnalysisRules. Got {type(rules)}"
            )

        if not isinstance(network, Network):
            raise TypeError(
                "'network' should of type DirectedNetwork or Network. "
                f"Got {type(network)}"
            )

        self.network.gdf = self.rules._validate_weight(self.network.gdf)

        self._check_if_holes_are_nan()

        if isinstance(self.network, DirectedNetwork):
            self.network._warn_if_undirected()

        self._update_wkts()
        self.rules._update_rules()

        if log:
            self.log = DataFrame()

    def _check_if_holes_are_nan(self):
        HOLES_ARE_NAN = (
            "Network holes have been filled by straigt lines, but the rows have "
            f"NaN values in the {self.rules.weight!r} column. Either remove NaNs "
            "or fill these values with a numeric value (e.g. 0)."
        )
        if hasattr(self.network, "_hole_col") and all(
            self.network.gdf[self.rules.weight].isna()
        ):
            raise ValueError(HOLES_ARE_NAN)

        if hasattr(self.network.gdf, "hole") and all(
            self.network.gdf[self.rules.weight].isna()
        ):
            raise ValueError(HOLES_ARE_NAN)

    def od_cost_matrix(
        self,
        origins: GeoDataFrame,
        destinations: GeoDataFrame,
        *,
        rowwise: bool = False,
        lines: bool = False,
    ) -> DataFrame | GeoDataFrame:
        """Fast calculation of many-to-many travel costs.

        Finds the the lowest cost (minutes, meters, etc.) from a set of origins to a
        set of destinations. The index of the origins and destinations are used as
        values for the returned columns 'origins' and 'destinations'.

        Args:
            origins: GeoDataFrame of points from where the trips will originate
            destinations: GeoDataFrame of points from where the trips will terminate
            rowwise: if False (default), it will calculate the cost from each
                origins to each destination. If true, it will calculate the cost from
                origin 1 to destination 1, origin 2 to destination 2 and so on.
            lines: if True, returns a geometry column with straight lines between
                origin and destination. Defaults to False.

        Returns:
            A DataFrame with the weight column and the columns 'origin' and
            'destination', containing the indices of the origins and destinations
            GeoDataFrames. If lines is True, also returns a geometry column with
            straight lines between origin and destination.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        Create some origin and destination points.

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")

        >>> origins = points.loc[:99, ["geometry"]]
        >>> origins
                                  geometry
        0   POINT (263122.700 6651184.900)
        1   POINT (272456.100 6653369.500)
        2   POINT (270082.300 6653032.700)
        3   POINT (259804.800 6650339.700)
        4   POINT (272876.200 6652889.100)
        ..                             ...
        95  POINT (270348.000 6651899.400)
        96  POINT (264845.600 6649005.800)
        97  POINT (263162.000 6650732.200)
        98  POINT (272322.700 6653729.100)
        99  POINT (265622.800 6644644.200)
        [100 rows x 1 columns]

        >>> destinations = points.loc[100:199, ["geometry"]]
        >>> destinations
                                   geometry
        100  POINT (265997.900 6647899.400)
        101  POINT (263835.200 6648677.700)
        102  POINT (265764.000 6644063.900)
        103  POINT (265970.700 6651258.500)
        104  POINT (264624.300 6649937.700)
        ..                              ...
        195  POINT (258175.600 6653694.300)
        196  POINT (258772.200 6652487.600)
        197  POINT (273135.300 6653198.100)
        198  POINT (270582.300 6652163.800)
        199  POINT (264980.800 6647231.300)
        [100 rows x 1 columns]

        Travel time from 100 to 100 points.

        >>> od = nwa.od_cost_matrix(origins, destinations)
        >>> od
              origin  destination    minutes
        0          0          100   8.765621
        1          0          101   6.383407
        2          0          102  13.482324
        3          0          103   6.410121
        4          0          104   5.882124
        ...      ...          ...        ...
        9995      99          195  20.488644
        9996      99          196  16.721241
        9997      99          197  19.977029
        9998      99          198  15.233163
        9999      99          199   6.439002
        [10000 rows x 3 columns]

        Join the results onto the 'origins' GeoDataFrame via the index.

        >>> joined = origins.join(od.set_index("origin"))
        >>> joined
                                  geometry  destination    minutes
        0   POINT (263122.700 6651184.900)          100   8.765621
        0   POINT (263122.700 6651184.900)          101   6.383407
        0   POINT (263122.700 6651184.900)          102  13.482324
        0   POINT (263122.700 6651184.900)          103   6.410121
        0   POINT (263122.700 6651184.900)          104   5.882124
        ..                             ...          ...        ...
        99  POINT (265622.800 6644644.200)          195  20.488644
        99  POINT (265622.800 6644644.200)          196  16.721241
        99  POINT (265622.800 6644644.200)          197  19.977029
        99  POINT (265622.800 6644644.200)          198  15.233163
        99  POINT (265622.800 6644644.200)          199   6.439002
        [10000 rows x 3 columns]

        Get travel times below 10 minutes.

        >>> less_than_10_min = od.loc[od.minutes < 10]
        >>> joined = origins.join(less_than_10_min.set_index("origin"))
        >>> joined
                                  geometry  destination   minutes
        0   POINT (263122.700 6651184.900)        100.0  8.765621
        0   POINT (263122.700 6651184.900)        101.0  6.383407
        0   POINT (263122.700 6651184.900)        103.0  6.410121
        0   POINT (263122.700 6651184.900)        104.0  5.882124
        0   POINT (263122.700 6651184.900)        106.0  9.811828
        ..                             ...          ...       ...
        99  POINT (265622.800 6644644.200)        173.0  4.305523
        99  POINT (265622.800 6644644.200)        174.0  6.094040
        99  POINT (265622.800 6644644.200)        177.0  5.944194
        99  POINT (265622.800 6644644.200)        183.0  8.449906
        99  POINT (265622.800 6644644.200)        199.0  6.439002
        [2195 rows x 3 columns]

        Get the three fastest routes from each origin.

        >>> three_fastest = od.loc[od.groupby("origin")["minutes"].rank() <= 3]
        >>> joined = origins.join(three_fastest.set_index("origin"))
        >>> joined
                                  geometry  destination   minutes
        0   POINT (263122.700 6651184.900)        135.0  0.966702
        0   POINT (263122.700 6651184.900)        175.0  2.202638
        0   POINT (263122.700 6651184.900)        188.0  2.931595
        1   POINT (272456.100 6653369.500)        171.0  2.918100
        1   POINT (272456.100 6653369.500)        184.0  2.754545
        ..                             ...          ...       ...
        98  POINT (272322.700 6653729.100)        184.0  3.175472
        98  POINT (272322.700 6653729.100)        189.0  3.179428
        99  POINT (265622.800 6644644.200)        102.0  1.648705
        99  POINT (265622.800 6644644.200)        134.0  1.116209
        99  POINT (265622.800 6644644.200)        156.0  1.368926
        [294 rows x 3 columns]

        Assign aggregated values directly onto the origins via the index.

        >>> origins["minutes_mean"] = od.groupby("origin")["minutes"].mean()
        >>> origins
                                  geometry  minutes_mean
        0   POINT (263122.700 6651184.900)     11.628637
        1   POINT (272456.100 6653369.500)     16.084722
        2   POINT (270082.300 6653032.700)     15.304246
        3   POINT (259804.800 6650339.700)     14.044023
        4   POINT (272876.200 6652889.100)     17.565747
        ..                             ...           ...
        95  POINT (270348.000 6651899.400)     15.427027
        96  POINT (264845.600 6649005.800)     11.239592
        97  POINT (263162.000 6650732.200)     11.904372
        98  POINT (272322.700 6653729.100)     17.579399
        99  POINT (265622.800 6644644.200)     12.185800
        [100 rows x 2 columns]

        Use set_index to use column as identifier insted of the index.

        >>> origins["letter"] = np.random.choice([*"abc"], len(origins))
        >>> od = nwa.od_cost_matrix(origins.set_index("letter"), destinations)
        >>> od
             origin  destination    minutes
        0         a          100   8.765621
        1         a          101   6.383407
        2         a          102  13.482324
        3         a          103   6.410121
        4         a          104   5.882124
        ...     ...          ...        ...
        9995      b          195  20.488644
        9996      b          196  16.721241
        9997      b          197  19.977029
        9998      b          198  15.233163
        9999      b          199   6.439002
        [10000 rows x 3 columns]

        Travel time from 1000 to 1000 points rowwise.

        >>> points_reversed = points.iloc[::-1].reset_index(drop=True)
        >>> od = nwa.od_cost_matrix(points, points_reversed, rowwise=True)
        >>> od
             origin  destination    minutes
        0         0            0  14.692667
        1         1            1   8.452691
        2         2            2  16.370569
        3         3            3   9.486131
        4         4            4  16.521346
        ..      ...          ...        ...
        995     995          995  16.794610
        996     996          996   9.611700
        997     997          997  19.968743
        998     998          998   9.484374
        999     999          999  14.892648
        [1000 rows x 3 columns]

        """
        if self._log:
            time_ = perf_counter()

        self._prepare_network_analysis(origins, destinations, rowwise)

        results = _od_cost_matrix(
            graph=self.graph,
            origins=self.origins.gdf,
            destinations=self.destinations.gdf,
            weight=self.rules.weight,
            lines=lines,
            rowwise=rowwise,
        )

        results["origin"] = results["origin"].map(self.origins.idx_dict)
        results["destination"] = results["destination"].map(self.destinations.idx_dict)

        if lines:
            results = _push_geom_col(results)

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "od_cost_matrix",
                results,
                minutes_elapsed,
                lines=lines,
                rowwise=rowwise,
            )

        return results

    def get_route(
        self,
        origins: GeoDataFrame,
        destinations: GeoDataFrame,
        *,
        rowwise: bool = False,
    ) -> GeoDataFrame:
        """Returns the geometry of the low-cost route between origins and destinations.

        Finds the route with the lowest cost (minutes, meters, etc.) from a set of
        origins to a set of destinations. If the weight is meters, the shortest route
        will be found. If the weight is minutes, the fastest route will be found.

        Args:
            origins: GeoDataFrame of points from where the routes will originate
            destinations: GeoDataFrame of points from where the routes will terminate.
            rowwise: if False (default), it will calculate the cost from each
                origins to each destination. If true, it will calculate the cost from
                origin 1 to destination 1, origin 2 to destination 2 and so on.

        Returns:
            A DataFrame with the geometry of the routes between origin and destination.
            Also returns a weight column and the columns 'origin' and 'destination',
            containing the indices of the origins and destinations GeoDataFrames.

        Raises:
            ValueError: if no paths were found.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        Get routes from 1 to 1000 points.

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")

        >>> routes = nwa.get_route(points.iloc[[0]], points)
        >>> routes
            origin  destination    minutes                                           geometry
        0         1            2  12.930588  MULTILINESTRING Z ((272281.367 6653079.745 160...
        1         1            3  10.867076  MULTILINESTRING Z ((270054.367 6653367.774 144...
        2         1            4   8.075722  MULTILINESTRING Z ((259735.774 6650362.886 24....
        3         1            5  14.659333  MULTILINESTRING Z ((272281.367 6653079.745 160...
        4         1            6  14.406460  MULTILINESTRING Z ((257034.948 6652685.595 156...
        ..      ...          ...        ...                                                ...
        992       1          996  10.858519  MULTILINESTRING Z ((266881.100 6647824.860 132...
        993       1          997   7.461032  MULTILINESTRING Z ((262623.190 6652506.640 79....
        994       1          998  10.698588  MULTILINESTRING Z ((263489.330 6645655.330 11....
        995       1          999  10.109855  MULTILINESTRING Z ((269217.997 6650654.895 166...
        996       1         1000  14.657289  MULTILINESTRING Z ((264475.675 6644245.782 114...

        [997 rows x 4 columns]
        """
        if self._log:
            time_ = perf_counter()

        self._prepare_network_analysis(origins, destinations, rowwise)

        results = _get_route(
            graph=self.graph,
            origins=self.origins.gdf,
            destinations=self.destinations.gdf,
            weight=self.rules.weight,
            roads=self.network.gdf,
            rowwise=rowwise,
        )

        results["origin"] = results["origin"].map(self.origins.idx_dict)
        results["destination"] = results["destination"].map(self.destinations.idx_dict)

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "get_route",
                results,
                minutes_elapsed,
                rowwise=rowwise,
            )

        return results

    def get_k_routes(
        self,
        origins: GeoDataFrame,
        destinations: GeoDataFrame,
        *,
        k: int,
        drop_middle_percent: int,
        rowwise=False,
    ) -> GeoDataFrame:
        """Returns the geometry of 1 or more routes between origins and destinations.

        Finds the route with the lowest cost (minutes, meters, etc.) from a set of
        origins to a set of destinations. Then the middle part of the route is removed
        from the graph the new low-cost path is found. Repeats k times. If k=1, it is
        identical to the get_route method.

        Note:
            How many percent of the route to drop from the graph, will determine how
            many k routes will be found. If 100 percent of the route is dropped, it is
            very hard to find more than one path for each OD pair. If
            'drop_middle_percent' is 1, the resulting routes might be very similar,
            depending on the layout of the network.

        Args:
            origins: GeoDataFrame of points from where the routes will originate
            destinations: GeoDataFrame of points from where the routes will terminate
            k: the number of low-cost routes to find
            drop_middle_percent: how many percent of the middle part of the routes
                that should be removed from the graph before the next k route is
                calculated. If set to 100, only the median edge will be removed.
                If set to 0, all but the first and last edge will be removed. The
                graph is copied for each od pair.
            rowwise: if False (default), it will calculate the cost from each
                origins to each destination. If true, it will calculate the cost from
                origin 1 to destination 1, origin 2 to destination 2 and so on.

        Returns:
            A DataFrame with the geometry of the k routes between origin and
            destination. Also returns the column 'k', a weight column and the columns
            'origin' and 'destination', containing the indices of the origins and
            destinations GeoDataFrames.

        Raises:
            ValueError: if no paths were found.
            ValueError: if drop_middle_percent is not between 0 and 100.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")
        >>> point1 = points.iloc[[0]]
        >>> point2 = points.iloc[[1]]

        Getting 10 fastest routes from one point to another point.

        >>> k_routes = nwa.get_k_routes(
        ...             point1,
        ...             point2,
        ...             k=10,
        ...             drop_middle_percent=1
        ...         )
        >>> k_routes
           origin  destination    minutes   k                                           geometry
        0       0            1  13.039830   1  MULTILINESTRING Z ((272281.367 6653079.745 160...
        1       0            1  14.084324   2  MULTILINESTRING Z ((272281.367 6653079.745 160...
        2       0            1  14.238108   3  MULTILINESTRING Z ((272281.367 6653079.745 160...
        3       0            1  14.897682   4  MULTILINESTRING Z ((271257.900 6654378.100 193...
        4       0            1  14.962593   5  MULTILINESTRING Z ((271257.900 6654378.100 193...
        5       0            1  15.423934   6  MULTILINESTRING Z ((272281.367 6653079.745 160...
        6       0            1  16.217271   7  MULTILINESTRING Z ((272281.367 6653079.745 160...
        7       0            1  16.483982   8  MULTILINESTRING Z ((272281.367 6653079.745 160...
        8       0            1  16.513253   9  MULTILINESTRING Z ((272281.367 6653079.745 160...
        9       0            1  16.551196  10  MULTILINESTRING Z ((272281.367 6653079.745 160...

        We got all 10 routes because only the middle 1 percent of the routes are
        removed in each iteration. Let's compare with dropping middle 50 and middle
        100 percent.

        >>> k_routes = nwa.get_k_routes(
        ...             point1,
        ...             point2,
        ...             k=10,
        ...             drop_middle_percent=50
        ...         )
        >>> k_routes
           origin  destination    minutes  k                                           geometry
        0       0            1  13.039830  1  MULTILINESTRING Z ((272281.367 6653079.745 160...
        1       0            1  14.238108  2  MULTILINESTRING Z ((272281.367 6653079.745 160...
        2       0            1  20.139294  3  MULTILINESTRING Z ((272281.367 6653079.745 160...
        3       0            1  23.506778  4  MULTILINESTRING Z ((265226.515 6650674.617 88....

        >>> k_routes = nwa.get_k_routes(
        ...             point1,
        ...             point2,
        ...             k=10,
        ...             drop_middle_percent=100
        ...         )
        >>> k_routes
           origin  destination   minutes  k                                           geometry
        0       0            1  13.03983  1  MULTILINESTRING Z ((272281.367 6653079.745 160...

        """
        if not 0 <= drop_middle_percent <= 100:
            raise ValueError("'drop_middle_percent' should be between 0 and 100")

        if self._log:
            time_ = perf_counter()

        self._prepare_network_analysis(origins, destinations, rowwise)

        results = _get_k_routes(
            graph=self.graph,
            origins=self.origins.gdf,
            destinations=self.destinations.gdf,
            weight=self.rules.weight,
            roads=self.network.gdf,
            rowwise=rowwise,
            k=k,
            drop_middle_percent=drop_middle_percent,
        )

        results["origin"] = results["origin"].map(self.origins.idx_dict)
        results["destination"] = results["destination"].map(self.destinations.idx_dict)

        if isinstance(results, GeoDataFrame):
            results = _push_geom_col(results)

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "get_k_routes",
                results,
                minutes_elapsed,
                rowwise=rowwise,
            )

        return results

    def get_route_frequencies(
        self,
        origins: GeoDataFrame,
        destinations: GeoDataFrame,
        weight_df: DataFrame | None = None,
        rowwise: bool = False,
        frequency_col: str = "frequency",
    ) -> GeoDataFrame:
        """Finds the number of times each line segment was visited in all trips.

        Finds the route with the lowest cost (minutes, meters, etc.) from a set of
        origins to a set of destinations and summarises the number of times each
        segment was used. The aggregation is done on the line indices, which is much
        faster than getting the geometries and then dissolving.

        The trip frequencies can be weighted (multiplied) based on 'weight_df'. See
        example below.

        Args:
            origins: GeoDataFrame of points from where the routes will originate.
            destinations: GeoDataFrame of points from where the routes will terminate.
            weight_df: A long formated DataFrame where each row contains the indices of
                an origin-destination pair and the number to multiply the frequency for
                this route by. The DataFrame can either contain three columns (origin
                index, destination index and weight. In that order) or only a weight
                column and a MultiIndex where level 0 is origin index and level 1 is
                destination index.
            frequency_col: Name of column with the number of times each road was
                visited. Defaults to 'frequency'.

        Returns:
            A GeoDataFrame with all line segments that were visited at least once,
            with a column with the number of times the line segment was used in the
            individual routes.

        Note:
            The resulting lines will keep all columns of the 'gdf' of the Network.

        Raises:
            ValueError: If no paths were found.
            ValueError: If weight_df is not a DataFrame with one or three columns.
            ValueError: If weight_df is given and the index of origins/destinations
                is not unique.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> import pandas as pd
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        Get number of times each road was visited for trips from 25 to 25 points.

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")

        >>> origins = points.iloc[:25]
        >>> destinations = points.iloc[25:50]
        >>> frequencies = nwa.get_route_frequencies(origins, destinations)
        >>> frequencies[["source", "target", "frequency", "geometry"]]
               source target  frequency                                           geometry
        160188  77264  79112        1.0  LINESTRING Z (268641.225 6651871.624 111.355, ...
        153682  68376   4136        1.0  LINESTRING Z (268542.700 6652162.400 121.266, ...
        153679  75263  75502        1.0  LINESTRING Z (268665.600 6652165.400 117.466, ...
        153678  75262  75263        1.0  LINESTRING Z (268660.000 6652167.100 117.466, ...
        153677  47999  75262        1.0  LINESTRING Z (268631.500 6652176.800 118.166, ...
        ...       ...    ...        ...                                                ...
        151465  73801  73802      103.0  LINESTRING Z (265368.600 6647142.900 131.660, ...
        151464  73800  73801      103.0  LINESTRING Z (265362.800 6647137.100 131.660, ...
        151466  73802  73632      103.0  LINESTRING Z (265371.400 6647147.900 131.660, ...
        151463  73799  73800      123.0  LINESTRING Z (265359.600 6647135.400 131.660, ...
        152170  74418  74246      130.0  LINESTRING Z (264579.835 6651954.573 113.209, ...

        [8556 rows x 4 columns]

        The frequencies can be weighted for each origin-destination pair by specifying
        'weight_df'. This can be a DataFrame with three columns, where the first two
        contain the indices of the origin and destination (in that order), and the
        third the number to multiply the frequency by. 'weight_df' can also be a
        DataFrame with a 2-leveled MultiIndex, where level 0 is the origin index and
        level 1 is the destination.

        Constructing a DataFrame with all od-pair combinations and give all rows a
        weight of 10.

        >>> od_pairs = pd.MultiIndex.from_product(
        ...     [origins.index, destinations.index], names=["origin", "destination"]
        ... )
        >>> weight_df = pd.DataFrame(index=od_pairs).reset_index()
        >>> weight_df["weight"] = 10
        >>> weight_df
             origin  destination  weight
        0         0           25      10
        1         0           26      10
        2         0           27      10
        3         0           28      10
        4         0           29      10
        ..      ...          ...     ...
        620      24           45      10
        621      24           46      10
        622      24           47      10
        623      24           48      10
        624      24           49      10

        [625 rows x 3 columns]

        All frequencies will now be multiplied by 10.

        >>> frequencies = nwa.get_route_frequencies(origins, destinations, weight_df, weight_df=weight_df)
        >>> frequencies[["source", "target", "frequency", "geometry"]]

               source target  frequency                                           geometry
        160188  77264  79112       10.0  LINESTRING Z (268641.225 6651871.624 111.355, ...
        153682  68376   4136       10.0  LINESTRING Z (268542.700 6652162.400 121.266, ...
        153679  75263  75502       10.0  LINESTRING Z (268665.600 6652165.400 117.466, ...
        153678  75262  75263       10.0  LINESTRING Z (268660.000 6652167.100 117.466, ...
        153677  47999  75262       10.0  LINESTRING Z (268631.500 6652176.800 118.166, ...
        ...       ...    ...        ...                                                ...
        151465  73801  73802     1030.0  LINESTRING Z (265368.600 6647142.900 131.660, ...
        151464  73800  73801     1030.0  LINESTRING Z (265362.800 6647137.100 131.660, ...
        151466  73802  73632     1030.0  LINESTRING Z (265371.400 6647147.900 131.660, ...
        151463  73799  73800     1230.0  LINESTRING Z (265359.600 6647135.400 131.660, ...
        152170  74418  74246     1300.0  LINESTRING Z (264579.835 6651954.573 113.209, ...

        [8556 rows x 4 columns]

        'weight_df' can also be a DataFrame with one column (the weight) and a
        MultiIndex.

        >>> weight_df = pd.DataFrame(index=od_pairs)
        >>> weight_df["weight"] = 10
        >>> weight_df
               weight
        0  25      10
           26      10
           27      10
           28      10
           29      10
        ...       ...
        24 45      10
           46      10
           47      10
           48      10
           49      10

        """
        if self._log:
            time_ = perf_counter()

        if weight_df is not None:
            weight_df = self._prepare_weight_df(weight_df, origins, destinations)

        self._prepare_network_analysis(origins, destinations, rowwise)

        if weight_df is not None:
            ori_idx_mapper = {v: k for k, v in self.origins.idx_dict.items()}
            des_idx_mapper = {v: k for k, v in self.destinations.idx_dict.items()}
            multiindex_mapper = lambda x: (
                ori_idx_mapper.get(x[0]),
                des_idx_mapper.get(x[1]),
            )
            weight_df.index = weight_df.index.map(multiindex_mapper)

        results = _get_route_frequencies(
            graph=self.graph,
            origins=self.origins.gdf,
            destinations=self.destinations.gdf,
            roads=self.network.gdf,
            weight_df=weight_df,
            rowwise=rowwise,
        )

        if isinstance(results, GeoDataFrame):
            results = _push_geom_col(results)

        results = results.rename(columns={"frequency": frequency_col}).sort_values(
            frequency_col
        )

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "get_route_frequencies",
                results,
                minutes_elapsed,
            )

        return results

    def service_area(
        self,
        origins: GeoDataFrame,
        breaks: int | float | tuple[int | float],
        *,
        dissolve: bool = True,
    ) -> GeoDataFrame:
        """Returns the lines that can be reached within breaks (weight values).

        It finds all the network lines that can be reached within each break. Lines
        that are only partly within the break will not be included. The index of the
        origins is used as values in the 'origins' column.

        Args:
            origins: GeoDataFrame of points from where the service areas will
                originate
            breaks: one or more integers or floats which will be the
                maximum weight for the service areas. Calculates multiple areas for
                each origins if multiple breaks.
            dissolve: If True (default), each service area will be dissolved into
                one long multilinestring. If False, the individual line segments will
                be returned.

        Returns:
            A GeoDataFrame with one row per break per origin, with the origin index and
            a dissolved line geometry. If dissolve is False, it will return each line
            that is part of the service area.

        See also:
            precice_service_area: Equivelent method where lines are also cut to get
                precice results.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        10 minute service area for three origin points.

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")
        >>> service_areas = nwa.service_area(
        ...         points.loc[:2],
        ...         breaks=10,
        ... )
        >>> service_areas
           origin  minutes                                           geometry
        0       0       10  MULTILINESTRING Z ((264348.673 6648271.134 17....
        1       1       10  MULTILINESTRING Z ((266909.769 6651075.250 114...
        2       2       10  MULTILINESTRING Z ((266909.769 6651075.250 114...

        Service areas of 5, 10 and 15 minutes from three origin points.

        >>> nwa = NetworkAnalysis(network=nw, rules=rules)
        >>> service_areas = nwa.service_area(
        ...         points.iloc[:2],
        ...         breaks=[5, 10, 15],
        ... )
        >>> service_areas
           origin  minutes                                           geometry
        0       0        5  MULTILINESTRING Z ((265378.000 6650581.600 85....
        1       0       10  MULTILINESTRING Z ((264348.673 6648271.134 17....
        2       0       15  MULTILINESTRING Z ((263110.060 6658296.870 154...
        3       1        5  MULTILINESTRING Z ((273330.930 6653248.870 208...
        4       1       10  MULTILINESTRING Z ((266909.769 6651075.250 114...
        5       1       15  MULTILINESTRING Z ((264348.673 6648271.134 17....
        """
        if self._log:
            time_ = perf_counter()

        self._prepare_network_analysis(origins)

        # sort the breaks as an np.ndarray
        breaks = self._sort_breaks(breaks)

        results = _service_area(
            graph=self.graph,
            origins=self.origins.gdf,
            breaks=breaks,
            weight=self.rules.weight,
            lines=self.network.gdf,
            nodes=self.network.nodes,
            directed=self.network._as_directed,
            precice=False,
        )

        if not all(results.geometry.isna()):
            results = results.drop_duplicates(["source_target_weight", "origin"])

            if dissolve:
                results = results.dissolve(by=["origin", self.rules.weight]).loc[
                    :, ["geometry"]
                ]

            results = results.reset_index()

            # add missing rows as NaNs
            missing = self.origins.gdf.loc[
                ~self.origins.gdf["temp_idx"].isin(results["origin"])
            ].rename(columns={"temp_idx": "origin"})[["origin"]]

            if len(missing):
                missing["geometry"] = np.nan
                results = pd.concat([results, missing], ignore_index=True)

            results["origin"] = results["origin"].map(self.origins.idx_dict)

            results = _push_geom_col(results)

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "service_area",
                results,
                minutes_elapsed,
                breaks=breaks,
                dissolve=dissolve,
            )

        return results

    def precice_service_area(
        self,
        origins: GeoDataFrame,
        breaks: int | float | tuple[int | float],
        *,
        dissolve: bool = True,
    ) -> GeoDataFrame:
        """Precice, but slow version of the service_area method.

        It finds all the network lines that can be reached within each break. Lines
        that are partly within the break will be split at the point where the weight
        value is exactly correct. Note that this takes more time than the regular
        'service_area' method.

        Args:
            origins: GeoDataFrame of points from where the service areas will
                originate
            breaks: one or more integers or floats which will be the
                maximum weight for the service areas. Calculates multiple areas for
                each origins if multiple breaks.
            dissolve: If True (default), each service area will be dissolved into
                one long multilinestring. If False, the individual line segments will
                be returned.

        Returns:
            A GeoDataFrame with one row per break per origin, with a dissolved line
            geometry. If dissolve is False, it will return all the columns of the
            network.gdf as well.

        See also:
            service_area: Faster method where lines are not cut to get precice results.

        Examples
        --------
        Create the NetworkAnalysis instance.

        >>> import sgis as sg
        >>> roads = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/roads_eidskog_2022.parquet")
        >>> nw = sg.DirectedNetwork(roads).remove_isolated().make_directed_network_norway()
        >>> rules = sg.NetworkAnalysisRules(weight="minutes")
        >>> nwa = sg.NetworkAnalysis(network=nw, rules=rules, detailed_log=False)

        10 minute service area for one origin point.

        >>> points = sg.read_parquet_url("https://media.githubusercontent.com/media/statisticsnorway/ssb-sgis/main/tests/testdata/points_oslo.parquet")

        >>> sa = nwa.precice_service_area(
        ...         points.iloc[[0]],
        ...         breaks=10,
        ...     )
        >>> sa
            idx  minutes                                           geometry
        0    1       10  MULTILINESTRING Z ((264348.673 6648271.134 17....

        Service areas of 5, 10 and 15 minutes from three origin points.

        >>> nwa = NetworkAnalysis(network=nw, rules=rules)
        >>> sa = nwa.precice_service_area(
        ...         points.iloc[:2],
        ...         breaks=[5, 10, 15],
        ...     )
        >>> sa
            idx  minutes                                           geometry
        0    1        5  MULTILINESTRING Z ((265378.000 6650581.600 85....
        1    1       10  MULTILINESTRING Z ((264348.673 6648271.134 17....
        2    1       15  MULTILINESTRING Z ((263110.060 6658296.870 154...
        3    2        5  MULTILINESTRING Z ((273330.930 6653248.870 208...
        4    2       10  MULTILINESTRING Z ((266909.769 6651075.250 114...
        5    2       15  MULTILINESTRING Z ((264348.673 6648271.134 17....
        """
        if self._log:
            time_ = perf_counter()

        self._prepare_network_analysis(origins)

        # sort the breaks as an np.ndarray
        breaks = self._sort_breaks(breaks)

        results = _service_area(
            graph=self.graph,
            origins=self.origins.gdf,
            breaks=breaks,
            weight=self.rules.weight,
            lines=self.network.gdf,
            nodes=self.network.nodes,
            directed=self.network._as_directed,
            precice=True,
        )

        if not all(results.geometry.isna()):
            results = results.drop_duplicates(["source_target_weight", "origin"])

            if dissolve:
                results = results.dissolve(by=["origin", self.rules.weight]).loc[
                    :, ["geometry"]
                ]

            results = results.reset_index()

            # add missing rows as NaNs
            missing = self.origins.gdf.loc[
                ~self.origins.gdf["temp_idx"].isin(results["origin"])
            ].rename(columns={"temp_idx": "origin"})[["origin"]]

            if len(missing):
                missing["geometry"] = np.nan
                results = pd.concat([results, missing], ignore_index=True)

            results["origin"] = results["origin"].map(self.origins.idx_dict)
            results = results.drop("origin", axis=1)

            results = _push_geom_col(results)

        if self.rules.split_lines:
            self._unsplit_network()

        if self._log:
            minutes_elapsed = round((perf_counter() - time_) / 60, 1)
            self._runlog(
                "service_area",
                results,
                minutes_elapsed,
                breaks=breaks,
                dissolve=dissolve,
            )

        return results

    @staticmethod
    def _prepare_weight_df(weight_df, origins, destinations):
        """Copy weight_df, convert to MultiIndex (if needed), then validate it.

        The weight_df needs to have a very specific shape and index. If a 3-columned df
        is given, convert the first two to a MultiIndex.

        Then make sure this index matches the index of origins and destinations.
        """
        error_message = (
            "'weight_df' should be a DataFrame with the columns "
            "'origin', 'destination' and 'weight', where the first "
            "two contain the indices of the origins and destinations "
            "and the weight column contains the number to multiply "
            "the trip frequency for this origin-destination pair."
        )

        if not isinstance(weight_df, DataFrame):
            raise ValueError(error_message)

        weight_df = weight_df.copy()

        if len(weight_df.columns) == 3:
            weight_df = weight_df.set_index(list(weight_df.columns[:2]))

        if len(weight_df.columns) != 1 and isinstance(weight_df.index, pd.MultiIndex):
            raise ValueError(error_message)

        if not weight_df.index.is_unique:
            raise ValueError("'weight_df' must contain only unique OD combinations.")

        if not origins.index.is_unique:
            raise ValueError(
                "The index of 'origins' must be unque when using a 'weight_df'."
            )
        if not destinations.index.is_unique:
            raise ValueError(
                "The index of 'destinations' must be unque when using a 'weight_df'."
            )

        # check if any/all indices are in origins/destinations.
        # Doing 'any' to give better error message
        level_0 = weight_df.index.get_level_values(0)
        if not level_0.isin(origins.index).any():
            raise ValueError("None of the 'origins' indices are in 'weight_df'.")

        level_1 = weight_df.index.get_level_values(1)
        if not level_1.isin(destinations.index).any():
            raise ValueError("None of the 'destinations' indices are in 'weight_df'.")

        if not level_0.isin(origins.index).all():
            raise ValueError("Not all 'origins' indices are in 'weight_df'.")

        if not level_1.isin(destinations.index).all():
            raise ValueError("Not all 'destinations' indices are in 'weight_df'.")

        return weight_df

    def _log_df_template(self, method: str, minutes_elapsed: float) -> DataFrame:
        """Creates a DataFrame with one row and the main columns.

        To be run after each network analysis.

        Args:
            method: the name of the network analysis method used
            minutes_elapsed: time use of the method

        Returns:
            A one-row DataFrame with log info columns

        Note:
            The 'isolated_removed' column does not account for
            preperation done before initialising the (Directed)Network class.
        """
        data = {
            "endtime": pd.to_datetime(datetime.now()).floor("S").to_pydatetime(),
            "minutes_elapsed": minutes_elapsed,
            "method": method,
            "origins_count": np.nan,
            "destinations_count": np.nan,
            "percent_missing": np.nan,
            "cost_mean": np.nan,
        }
        if self.detailed_log:
            data = data | {
                "isolated_removed": self.network._isolated_removed,
                "percent_bidirectional": self.network.percent_bidirectional,
            }

        df = DataFrame(data, index=[0])

        if not self.detailed_log:
            return df

        for key, value in self.rules.__dict__.items():
            if key.startswith("_") or key.endswith("_"):
                continue
            df = pd.concat([df, pd.DataFrame({key: [value]})], axis=1)

        return df

    def _runlog(
        self,
        fun: str,
        results: DataFrame | GeoDataFrame,
        minutes_elapsed: float,
        **kwargs,
    ) -> None:
        df = self._log_df_template(fun, minutes_elapsed)

        df["origins_count"] = len(self.origins.gdf)

        if self.rules.weight in results.columns:
            df["percent_missing"] = results[self.rules.weight].isna().mean() * 100
            df["cost_mean"] = results[self.rules.weight].mean()
            if self.detailed_log:
                df["cost_p25"] = results[self.rules.weight].quantile(0.25)
                df["cost_median"] = results[self.rules.weight].median()
                df["cost_p75"] = results[self.rules.weight].quantile(0.75)
                df["cost_std"] = results[self.rules.weight].std()

        if fun == "service_area":
            df["percent_missing"] = results["geometry"].isna().mean() * 100
        else:
            df["destinations_count"] = len(self.destinations.gdf)

        if self.detailed_log:
            for key, value in kwargs.items():
                if isinstance(value, np.ndarray):
                    value = list(value)
                if isinstance(value, (list, tuple)):
                    value = [str(x) for x in value]
                    value = ", ".join(value)
                df[key] = value

        self.log = pd.concat([self.log, df], ignore_index=True)

    def _prepare_network_analysis(
        self, origins, destinations=None, rowwise=False
    ) -> None:
        """Prepares the weight column, node ids, origins, destinations and graph.

        Updates the graph only if it is not yet created and no parts of the analysis
        has changed. this method is run inside od_cost_matrix, get_route and
        service_area.
        """

        if rowwise and len(origins) != len(destinations):
            raise ValueError(
                "'origins' and 'destinations' must have the same length when "
                "rowwise=True"
            )

        self.network.gdf = self.rules._validate_weight(self.network.gdf)

        self.origins = Origins(origins)
        self.origins._make_temp_idx(
            start=max(self.network.nodes.node_id.astype(int)) + 1
        )

        if destinations is not None:
            self.destinations = Destinations(destinations)
            self.destinations._make_temp_idx(
                start=max(self.origins.gdf.temp_idx.astype(int)) + 1
            )

        else:
            self.destinations = None

        if not self._graph_is_up_to_date() or not self.network._nodes_are_up_to_date():
            self.network._update_nodes_if()

            edges, weights, ids = self._get_edges_and_weights()

            self.graph = self._make_graph(
                edges=edges,
                weights=weights,
                edge_ids=ids,
                directed=self.network._as_directed,
            )

            self._add_missing_vertices()

        self._update_wkts()
        self.rules._update_rules()

    def _get_edges_and_weights(
        self,
    ) -> tuple[list[tuple[str, str]], list[float], list[str]]:
        """Creates lists of edges and weights which will be used to make the graph.

        Edges and weights between origins and nodes and nodes and destinations are
        also added.
        """
        if self.rules.split_lines:
            self._split_lines()
            self.network._make_node_ids()
            self.origins._make_temp_idx(
                start=max(self.network.nodes.node_id.astype(int)) + 1
            )
            if self.destinations is not None:
                self.destinations._make_temp_idx(
                    start=max(self.origins.gdf.temp_idx.astype(int)) + 1
                )

        edges: list[tuple[str, str]] = self.network.get_edges()

        weights = list(self.network.gdf[self.rules.weight])

        self.network.gdf["source_target_weight"] = self.network._create_edge_ids(
            edges, weights
        )

        edges_start, weights_start = self.origins._get_edges_and_weights(
            nodes=self.network.nodes,
            rules=self.rules,
        )

        edges = edges + edges_start
        weights = weights + weights_start

        if self.destinations is None:
            edge_ids = self.network._create_edge_ids(edges, weights)
            return edges, weights, edge_ids

        edges_end, weights_end = self.destinations._get_edges_and_weights(
            nodes=self.network.nodes,
            rules=self.rules,
        )

        edges = edges + edges_end
        weights = weights + weights_end

        edge_ids = self.network._create_edge_ids(edges, weights)

        return edges, weights, edge_ids

    def _split_lines(self) -> None:
        if self.destinations is not None:
            points = pd.concat(
                [self.origins.gdf, self.destinations.gdf], ignore_index=True
            )
        else:
            points = self.origins.gdf

        points = points.drop_duplicates("geometry")

        self.network.gdf["meters_"] = self.network.gdf.length

        # create an id from before the split, used to revert the split later
        self.network.gdf["temp_idx__"] = range(len(self.network.gdf))

        lines = split_lines_by_nearest_point(
            lines=self.network.gdf,
            points=points,
            max_distance=self.rules.search_tolerance,
        )

        # save the unsplit lines for later
        splitted = lines.loc[lines["splitted"] == 1, "temp_idx__"]
        self.network._not_splitted = self.network.gdf.loc[
            self.network.gdf["temp_idx__"].isin(splitted)
        ]

        # adjust weight to new length
        lines[self.rules.weight] = lines[self.rules.weight] * (
            lines.length / lines["meters_"]
        )

        self.network.gdf = lines

    def _unsplit_network(self):
        """Remove the splitted lines and add the unsplitted ones."""
        lines = self.network.gdf.loc[self.network.gdf.splitted != 1]
        self.network.gdf = pd.concat(
            [lines, self.network._not_splitted], ignore_index=True
        ).drop("temp_idx__", axis=1)
        del self.network._not_splitted

    def _add_missing_vertices(self):
        """Adds the missing points.

        Nodes that had no nodes within the search_tolerance are added to the graph.
        To not get an error when running the distance calculation.
        """
        # TODO: either check if any() beforehand, or add fictional edges before
        # making the graph, to make things faster
        # (this method took 64.660 out of 500 seconds)
        self.graph.add_vertices(
            [
                idx
                for idx in self.origins.gdf["temp_idx"]
                if idx not in self.graph.vs["name"]
            ]
        )
        if self.destinations is not None:
            self.graph.add_vertices(
                [
                    idx
                    for idx in self.destinations.gdf["temp_idx"]
                    if idx not in self.graph.vs["name"]
                ]
            )

    @staticmethod
    def _make_graph(
        edges: list[tuple[str, ...]] | np.ndarray[tuple[str, ...]],
        weights: list[float] | np.ndarray[float],
        edge_ids: np.ndarray,
        directed: bool,
    ) -> Graph:
        """Creates an igraph Graph from a list of edges and weights."""
        assert len(edges) == len(weights)

        graph = igraph.Graph.TupleList(edges, directed=directed)

        graph.es["weight"] = weights
        graph.es["source_target_weight"] = edge_ids
        graph.es["edge_tuples"] = edges
        graph.es["source"] = [edge[0] for edge in edges]
        graph.es["target"] = [edge[1] for edge in edges]

        assert min(graph.es["weight"]) >= 0

        return graph

    def _graph_is_up_to_date(self) -> bool:
        """Checks if the network or rules have changed.

        Returns False if the rules of the graphmaking has changed,
        or if the points have changed.
        """
        if not hasattr(self, "graph") or not hasattr(self, "wkts"):
            return False

        if self.rules._rules_have_changed():
            return False

        for points in ["origins", "destinations"]:
            if not hasattr(self.wkts, points):
                return False
            if self._points_have_changed(self[points].gdf, what=points):
                return False

        #        if not self.gdf["source_target_weight"].
        return True

    def _points_have_changed(self, points: GeoDataFrame, what: str) -> bool:
        """Check if the origins or destinations have changed.

        This method is best stored in the NetworkAnalysis class,
        since the point classes are instantiated each time an analysis is run.
        """
        if self.wkts[what] != [geom.wkt for geom in points.geometry]:
            return True

        if not all(x in self.graph.vs["name"] for x in list(points.temp_idx.values)):
            return True

        return False

    def _update_wkts(self) -> None:
        """Creates a dict of wkt lists.

        This method is run after the graph is created. If the wkts haven't updated
        since the last run, the graph doesn't have to be remade.
        """
        self.wkts = {}

        self.wkts["network"] = [geom.wkt for geom in self.network.gdf.geometry]

        if not hasattr(self, "origins"):
            return

        self.wkts["origins"] = [geom.wkt for geom in self.origins.gdf.geometry]

        if self.destinations is not None:
            self.wkts["destinations"] = [
                geom.wkt for geom in self.destinations.gdf.geometry
            ]

    @staticmethod
    def _sort_breaks(breaks) -> list[float | int]:
        if isinstance(breaks, str):
            breaks = float(breaks)

        if hasattr(breaks, "__iter__"):
            return list(sorted(list(breaks)))

        if isinstance(breaks, (int, float)):
            return [breaks]

        raise ValueError(
            "'breaks' should not integer, float, string or an iterable of "
            f" one of these. Got {type(breaks)!r}"
        )

    def __repr__(self) -> str:
        """The print representation."""
        # drop the 'weight_to_nodes_' parameters in the repr of rules to avoid clutter
        rules = (
            f"{self.rules.__class__.__name__}(weight={self.rules.weight}, "
            f"search_tolerance={self.rules.search_tolerance}, "
            f"search_factor={self.rules.search_factor}, "
            f"split_lines={self.rules.split_lines}, "
        )

        # add one 'weight_to_nodes_' parameter if used,
        # else inform that there are more parameters with '...'
        if self.rules.nodedist_multiplier:
            x = f"nodedist_multiplier={self.rules.nodedist_multiplier}"
        elif self.rules.nodedist_kmh:
            x = f"nodedist_kmh={self.rules.nodedist_kmh}"
        else:
            x = "..."

        return (
            f"{self.__class__.__name__}(\n"
            f"    network={self.network.__repr__()},\n"
            f"    rules={rules}{x}),\n"
            f"    log={self._log}, detailed_log={self.detailed_log},"
            "\n)"
        )

    def __getitem__(self, item):
        """To be able to write self['origins'] as well as self.origins."""
        return getattr(self, item)

    def copy(self):
        """Returns a shallow copy of the class instance."""
        return copy(self)

    def deepcopy(self):
        """Returns a deep copy of the class instance."""
        return deepcopy(self)
