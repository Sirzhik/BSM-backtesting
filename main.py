from AlgorithmImports import *
from BSM import call_formula


class AutomaticImpliedVolatilityIndicatorAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2019, 1, 1)
        self.set_end_date(2025, 11, 26)
        self.set_cash(200000)

        self.set_security_initializer(
            BrokerageModelSecurityInitializer(
                self.brokerage_model, 
                FuncSecuritySeeder(self.get_last_known_prices)
            )
        )

        self._underlying = self.add_equity('SPY', data_normalization_mode=DataNormalizationMode.RAW).symbol
        self.set_benchmark('SPY')

        self.schedule.on(
            self.date_rules.every_day(self._underlying),
            self.time_rules.at(9, 0),
            self._update_contracts_and_greeks
        )
        self._options = None

    def _update_contracts_and_greeks(self) -> None:
        if self._underlying is None:
            return

        chain = self.option_chain(self._underlying, flatten=True).data_frame
        if chain.empty:
            return

        chain = chain[
            (chain.expiry > self.time + timedelta(10)) &
            (chain.expiry < self.time + timedelta(90))
        ]

        self.expiry = chain.expiry.min()
        chain = chain[chain.expiry == self.expiry]

        chain.loc[:, 'abs_strike_delta'] = abs(chain['strike'] - chain['underlyinglastprice'])

        min_delta = chain.loc[:, 'abs_strike_delta'].min()
        chain = chain[chain['abs_strike_delta'] == min_delta]

        contracts_pair_sizes = chain.groupby(['expiry', 'strike']).count()['right']
        paired_contracts = contracts_pair_sizes[contracts_pair_sizes == 2].index
        expiries = [x[0] for x in paired_contracts]
        strikes = [x[1] for x in paired_contracts]
        symbols = [
            idx[-1] for idx in chain[
                chain['expiry'].isin(expiries) & chain['strike'].isin(strikes)
            ].reset_index().groupby(['expiry', 'strike', 'right', 'symbol']).first().index
        ]
        pairs = [(symbols[i], symbols[i+1]) for i in range(0, len(symbols), 2)]

        for call, _ in pairs:
            contract1 = self.add_option_contract(call)
            # contract2 = self.add_option_contract(put)
            
            self.histPrice = (contract1.bid_price + contract1.ask_price) / 2
            self.strike = contract1.strike_price
            self.underlying = self.Securities[self._underlying].Price
            
            # contract1.iv = self.iv(call, put)
            contract1.iv = self.iv(call)
            self.IV = contract1.iv

            self._options = call
        
    def on_data(self, slice: Slice) -> None:
        rfi = self.risk_free_interest_rate_model.get_interest_rate(self.time)
        timeToExparation = (self.expiry - self.time).total_seconds() / (3600 * 24 * 365)

        BSMresult = call_formula(
            stockPrice=self.underlying, 
            volatility=self.IV.Current.Value, 
            strikePrice=self.strike,
            timeToExpiration=timeToExparation,
            riskFreeInterestRate=rfi)
            
        if BSMresult > self.histPrice * 1.2:
            self.debug(f'underlying: {self.underlying}')
            self.debug(f'BSM: {BSMresult}')
            self.debug(f'histPrice: {self.histPrice}')
            self.debug(f'strike: {self.strike}')

        if not self.portfolio.invested and self._options and abs(self.strike - self.underlying) <= 1 and BSMresult > self.histPrice * 1.2:
            self.sell(self._options, 15)
        if self.portfolio[self._underlying].invested:
            self.liquidate(self._underlying)
