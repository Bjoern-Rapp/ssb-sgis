# %%
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


src = str(Path(__file__).parent).strip("tests") + "src"

sys.path.insert(0, src)

import sgis as sg


def test_k_neighbors(points_oslo):
    p = points_oslo

    p["idx"] = p.index
    p["idx2"] = np.random.randint(10_000, 20_000, size=len(p))

    with pytest.raises(ValueError):
        sg.get_neighbor_indices(gdf=p, neighbors=p.to_crs(4326))
    with pytest.raises(ValueError):
        sg.get_k_nearest_neighbors(gdf=p, neighbors=p.to_crs(4326), k=50)
    with pytest.raises(ValueError):
        sg.get_all_distances(gdf=p, neighbors=p.to_crs(4326))

    df = sg.get_k_nearest_neighbors(
        gdf=p,
        neighbors=p,
        k=50,
    )
    print(df)
    assert len(df) == len(p) * 50
    assert max(df.index) == 999

    df_from_geoseries = sg.get_k_nearest_neighbors(
        gdf=p.geometry,
        neighbors=p.geometry,
        k=50,
    )

    assert df.equals(df_from_geoseries)

    p2 = p.join(df)
    assert len(p2) == len(p) * 50
    p2["k"] = p2.groupby(level=0)["distance"].transform("rank")
    assert max(p2.k) == 50
    assert min(p2.k) == 1
    print(p2)

    p["mean_distance"] = df.groupby(level=0)["distance"].mean()
    p["min_distance"] = df.groupby(level=0)["distance"].min()
    print(p)

    df = sg.get_k_nearest_neighbors(
        gdf=p,
        neighbors=p.set_index("idx2"),
        k=50,
    )
    print(df)
    assert len(df) == len(p) * 50
    assert max(df.index) == 999

    df = sg.get_k_nearest_neighbors(
        gdf=p,
        neighbors=p.set_index("idx2"),
        k=50,
    )
    print(df)
    assert len(df) == len(p) * 50
    assert max(df.index) == 999

    df = sg.get_k_nearest_neighbors(
        gdf=p.assign(a="a").set_index("a"),
        neighbors=p.set_index("idx2"),
        k=50,
    )
    assert all(df.index == "a")
    assert len(df) == len(p) * 50

    # should preserve index name
    p = p.rename_axis("point_idx", axis=0)
    df = sg.get_k_nearest_neighbors(p, p, k=10)
    assert df.index.name == "point_idx"

    # too many points should be ok when strict is False
    df = sg.get_k_nearest_neighbors(
        gdf=p,
        neighbors=p,
        k=10_000,
    )

    try:
        df = sg.get_k_nearest_neighbors(
            gdf=p,
            neighbors=p,
            k=10_000,
            strict=True,
        )
        failed = False
    except ValueError:
        failed = True
    assert failed

    df = sg.get_all_distances(
        gdf=p,
        neighbors=p.set_index("idx2"),
    )

    print(df)

    assert len(df) == len(p) * len(p)

    # should give exact same results with geoseries
    df_from_geoseries = sg.get_all_distances(
        gdf=p.geometry,
        neighbors=p.set_index("idx2").geometry,
    )

    print(df_from_geoseries)

    assert df.equals(df_from_geoseries)

    # from array of geometries to arrays of distances and indices
    distances, indices = sg.k_nearest_neighbors(
        sg.coordinate_array(p), sg.coordinate_array(p)
    )
    assert isinstance(distances, np.ndarray)
    assert isinstance(indices, np.ndarray)
    distances2, indices2 = sg.k_nearest_neighbors(
        sg.coordinate_array(p.geometry), sg.coordinate_array(p.geometry)
    )
    assert np.array_equal(distances, distances2)
    assert np.array_equal(indices, indices2)


def test_get_neighbor_indices():
    points = sg.to_gdf([(0, 0), (0.5, 0.5), (2, 2)])
    p1 = points.iloc[[0]]

    neighbor_indices = sg.get_neighbor_indices(p1, points)
    assert neighbor_indices.equals(pd.Series([0], index=[0]))

    neighbor_indices = sg.get_neighbor_indices(p1, points, max_distance=1)
    assert neighbor_indices.equals(pd.Series([0, 1], index=[0, 0]))

    neighbor_indices = sg.get_neighbor_indices(p1, points, max_distance=3)
    assert neighbor_indices.equals(pd.Series([0, 1, 2], index=[0, 0, 0]))

    points["id_col"] = [*"abc"]
    neighbor_indices = sg.get_neighbor_indices(
        p1, points.set_index("id_col"), max_distance=3
    )
    assert neighbor_indices.equals(pd.Series(["a", "b", "c"], index=[0, 0, 0]))

    two_points = sg.to_gdf([(0, 0), (0.5, 0.5)])
    two_points["text"] = [*"ab"]
    neighbor_indices = sg.get_neighbor_indices(two_points, two_points)
    assert neighbor_indices.equals(pd.Series([0, 1], index=[0, 1]))

    neighbor_indices = sg.get_neighbor_indices(two_points, two_points, max_distance=1)
    assert neighbor_indices.equals(pd.Series([0, 0, 1, 1], index=[0, 1, 0, 1]))

    neighbor_indices = sg.get_neighbor_indices(
        two_points, two_points.set_index("text"), max_distance=1
    )
    assert neighbor_indices.equals(pd.Series(["a", "a", "b", "b"], index=[0, 1, 0, 1]))

    assert list(neighbor_indices.values) == ["a", "a", "b", "b"]
    assert list(neighbor_indices.index) == [0, 1, 0, 1]

    neighbor_indices = sg.get_neighbor_indices(
        two_points, two_points.set_index("text"), predicate="nearest"
    )
    assert neighbor_indices.equals(pd.Series(["a", "b"], index=[0, 1]))
    assert list(neighbor_indices.values) == ["a", "b"]
    assert list(neighbor_indices.index) == [0, 1]

    neighbor_indices = sg.get_neighbor_indices(
        two_points.iloc[[0]],
        two_points.iloc[[1]],
        predicate="nearest",
        max_distance=0.5,
    )
    assert not len(neighbor_indices)


def main():
    from oslo import points_oslo

    points_oslo = points_oslo()

    test_k_neighbors(points_oslo)
    test_get_neighbor_indices()


if __name__ == "__main__":
    main()
