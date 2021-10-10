from abc import ABC
import pandas as pd

from .backtest_tear import BacktestTear
from .. import plotter
from .. import utils

from ntiles.portals.base_portal import BaseGrouperPortalConstant


class TiltsBacktestTear(BacktestTear, ABC):
    """
    generates a tear sheet which shows the sector exposures of a strategy
    Must be run after the backtest tear
    """

    def __init__(self, ntile_matrix: pd.DataFrame, daily_returns: pd.DataFrame, ntiles, holding_period: int,
                 long_short: bool, market_neutral: bool, show_plots: bool, show_uni: bool,
                 factor_data: pd.DataFrame, group_portal: BaseGrouperPortalConstant, show_ntile_tilts: bool):

        super().__init__(ntile_matrix, daily_returns, ntiles, holding_period, long_short, market_neutral, show_plots,
                         show_uni)
        self._factor_data = factor_data
        self._group_portal = group_portal
        self._show_ntile_tilts = show_ntile_tilts

        self._daily_group_weights = {}
        self._full_group_tilt_avg = {}

    def compute(self) -> None:
        """
        master function for the tear sheet
        :return: None
        """
        super().compute()

        if (self._group_portal is not None) and (not self._show_ntile_tilts):
            self.compute_tilts()
            self.compute_plots()

    def compute_tilts(self):
        """
        computes the daily tilt data for each group
        :return: None
        """
        self.compute_group_weights()
        if self.long_short:
            self.calculate_long_short_tilts()

    def compute_group_weights(self):
        """
        computes the weights by group for each ntile
        currently computes data but work because need a time series data adjusted for index constitutes
        have to use self.factor_data
        :return: None
        """
        group_info = self._group_portal.group_information
        center_weight = group_info.groupby(group_info).count() / group_info.shape[0]
        center_weight = utils.remove_cat_index(center_weight)

        if self._show_ntile_tilts:
            ntile_keys = self.daily_weights.keys()
        else:
            ntile_keys = [min(self.daily_weights.keys()), max(self.daily_weights.keys())]

        new_col = self.daily_weights[ntile_keys[0]].columns.astype(str).map(self._group_portal.group_mapping)

        for ntile in ntile_keys:
            frame = self.daily_weights[ntile]
            frame.columns = new_col
            frame = self.daily_weights[ntile].stack().to_frame('weight')
            frame.index.names = ['date', 'group']

            weights_unstacked = frame.groupby(['date', 'group']).sum().sub(center_weight, level=1, axis=0).unstack()
            weights_unstacked.columns = weights_unstacked.columns.droplevel(0)

            self._daily_group_weights[ntile] = weights_unstacked
            self._full_group_tilt_avg[ntile] = (frame.groupby('group').sum().weight
                                                / frame.index.levels[0].unique().shape[0]
                                                - center_weight)

    def calculate_long_short_tilts(self):
        """
        calculates the time series tilts for the long short portfolio
        :return: None
        """
        ntile_n = max(self._daily_group_weights.keys())
        self._daily_group_weights['Long Short'] = (self._daily_group_weights['Ntile: 1']
                                                   - self._daily_group_weights[ntile_n])
        self._full_group_tilt_avg['Long Short'] = self._daily_group_weights['Long Short'].stack().groupby(
            'group').mean()

    def compute_plots(self):
        print('Weights By Group')
        for ntile in self._daily_group_weights.keys():
            if 'Long Short' == ntile and not self.long_short:
                continue
            if 'Ntile' in ntile and not self._show_ntile_tilts:
                continue
            ax = plotter.plot_tilt_hist(self._full_group_tilt_avg[ntile], ntile, self._group_portal.name)
            plotter.plot_tilts(self._daily_group_weights[ntile], ntile, self._group_portal.name, ax)
