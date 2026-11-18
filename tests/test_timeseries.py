import numpy as np
import pandas as pd
import pytest

from aeron import timeseries as ts


def ar1(n, phi, seed=0):
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    return pd.Series(x, index=pd.date_range("2020-01-01", periods=n, freq="D"))


def test_acf_of_ar1_is_phi_to_the_k():
    acf = ts.pairwise_acf(ar1(20000, 0.7), 4)
    assert acf == pytest.approx([0.7, 0.49, 0.343, 0.24], abs=0.03)


def test_pairwise_acf_ignores_gaps_without_filling_them():
    x = ar1(20000, 0.7)
    x[x.index[::7]] = np.nan  # a gap every 7th day
    acf = ts.pairwise_acf(x, 2)
    assert acf == pytest.approx([0.7, 0.49], abs=0.04)


def test_pacf_of_ar1_cuts_off_after_lag_one():
    acf = ts.pairwise_acf(ar1(30000, 0.6), 6)
    pacf = ts.pacf_from_acf(acf)
    assert pacf[0] == pytest.approx(0.6, abs=0.03)
    assert np.abs(pacf[1:]).max() < 0.05


def test_pacf_matches_known_ar2():
    # AR(2) with phi1 = 0.5, phi2 = 0.3: autocorrelations from the Yule-Walker equations.
    rho1 = 0.5 / (1 - 0.3)
    rho2 = 0.5 * rho1 + 0.3
    pacf = ts.pacf_from_acf(np.array([rho1, rho2]))
    assert pacf[0] == pytest.approx(rho1)
    assert pacf[1] == pytest.approx(0.3)


def test_effective_sample_size_of_ar1():
    phi = 0.5
    acf = np.array([phi**k for k in range(1, 40)])
    # Stops at the floor, so compare with the exact value n (1 - phi) / (1 + phi).
    assert ts.effective_sample_size(1000, acf, floor=1e-6) == pytest.approx(
        1000 * (1 - phi) / (1 + phi), rel=0.01
    )
    assert (
        ts.effective_sample_size(1000, np.array([0.0, 0.5])) == 1000
    )  # stops at the first small lag


def test_runs_of_observed():
    s = pd.Series([1, 2, np.nan, 3, np.nan, np.nan, 4, 5, 6])
    assert ts.runs_of_observed(s).tolist() == [3, 2, 1]


def test_seasonal_climatology_recovers_a_yearly_cycle():
    index = pd.date_range("2019-01-01", "2023-12-31", freq="D")
    cycle = 10 + 5 * np.sin(2 * np.pi * index.day_of_year / 365.25)
    clim = ts.seasonal_climatology(pd.Series(cycle, index=index))
    assert len(clim) == 366
    assert clim.loc[91] == pytest.approx(
        10 + 5 * np.sin(2 * np.pi * 91 / 365.25), abs=0.3
    )
