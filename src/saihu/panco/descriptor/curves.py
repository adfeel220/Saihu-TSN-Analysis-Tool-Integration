#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of the panco project.
# https://github.com/Huawei-Paris-Research-Center/Panco

from __future__ import annotations

__author__ = "Anne Bouillard"
__maintainer__ = "Anne Bouillard"
__email__ = "anne.bouillard@huawei.com"
__copyright__ = "Copyright (C) 2022, Huawei Technologies France"
__license__ = "BSD-3"

from typing import List, Tuple
import numpy as np


class RateLatency:
    """
    The RateLatency class encodes the rate-latency class of functions, for minimum service curves,
    :math:`\\beta(t) = R(t-T)_+`.

    :param latency: the latency term :math:`T`
    :type latency: float
    :param rate: the service rate term :math:`R`
    :type rate: float


    >>> RateLatency(5, 4)
    5(t - 4)_+
    """

    def __init__(self, rate: float, latency: float):
        self.latency = latency
        self.rate = rate

    def __str__(self):
        return str(self.rate) + '(t - ' + str(self.latency) + ')_+'

    def __repr__(self) -> str:
        return "%s" % self.__str__()

    def __eq__(self, other: RateLatency):
        return (self.latency == other.latency) and (self.rate == other.rate)

    def evaluate(self, t: float) -> float:
        """
        Evaluates the rate-latency function at :math:`t`: :math:`\\beta(t) = R \\max(t-T)_+`.

        :param t: the value which the function is computed
        :type t: float
        :return: :math:`\\beta(t)`
        :rtype: float
        """
        return max(0., self.rate * (t - self.latency))


class TokenBucket:
    """
    The TokenBucket class encodes the token-bucket class of functions, for arrival curves and maximum service curves,
    :math:`\\alpha(t) = \\sigma + \\rho t`.

    :param sigma: the burst term :math:`\\sigma`
    :type sigma: float
    :param rho: the maximum arrival/service rate term :math:`\\rho`
    :type rho: float


    >>> TokenBucket(5, 4)
    5 + 4t
    """

    def __init__(self, sigma: float, rho: float):
        self.sigma = sigma
        self.rho = rho

    def __str__(self):
        return str(self.sigma) + ' + ' + str(self.rho) + 't'

    def __repr__(self) -> str:
        return "%s" % self.__str__()

    def __eq__(self, other):
        return (self.sigma == other.sigma) and (self.rho == other.rho)

    def evaluate(self, t: float) -> float:
        """
        Evaluates the token-bucket function at :math:`t`: :math:`\\gamma(t) = \\sigma + \\rho t`.

        :param t: the value which the function is computed
        :type t: float
        :return: :math:`\\gamma(t)`
        :rtype: float
        """
        return self.sigma + self.rho * t

    def scale(self, factor: float) -> TokenBucket:
        """
        Scales the token-bucket curve :math:`\\alpha` by a factor :math:`f`: the returned token-bucket is then \\
        :math:`f \\alpha`.
        :param factor: the value of the factor :math:`f`
        :type factor: float
        :return: :math:`f \\alpha`
        :rtype: TokenBucket

        >>> TokenBucket(2, 3).scale(2)
        4 + 6t
        """
        return TokenBucket(factor * self.sigma, factor * self.rho)

    def delay(self, delta: float) -> TokenBucket:
        """
        Computes the deconvolution with a pure delay curve (dive by the delay parameter :math:`\\delta`):\\
        :math:`\\gamma_{\\sigma, \\rho} \\oslash \\Delta_\\delta = \\gamma_{\\sigma + \\delta \\rho, \\rho}`

        :param delta: the delay parameter :math:`\\delta`):\\
        :return: the Token Bucket curve :math:`\\gamma_{\\sigma, \\rho} \\oslash \\Delta_\\delta`

        >>> TokenBucket(3, 2).delay(4)
        11 + 2t
        """
        return TokenBucket(self.sigma + self.rho * delta, self.rho)


def tb_sum(list_tb: List[TokenBucket]) -> TokenBucket:
    """
    Computes the sum of the token-bucket in :math:`\\alpha_i(t) = \\sigma_i + \\rho_i t` in list_tb: \\
    :math:`\\alpha(t) = \\sum_{i=1}^n \\alpha_i(t) = \\sum_{i=1}^n \\sigma_i + (\\sum_{i=1}^n \\rho_i) t`

    :param list_tb: a list of token_bucket :math:
    :type list_tb: List[TokenBuckets]
    :return: The sum of the arrival curves in list_tb :math:`\\alpha`.


    >>> tb_sum([TokenBucket(1, 2), TokenBucket(3, 4), TokenBucket(5, 6)])
    9 + 12t
    >>> tb_sum([TokenBucket(np.inf, 2), TokenBucket(3, 4)])
    inf + 6t
    >>> tb_sum([])
    0 + 0t
    """
    return TokenBucket(sigma=sum(x.sigma for x in list_tb), rho=sum(x.rho for x in list_tb))


def residual_blind(rl: RateLatency, tb: TokenBucket) -> RateLatency:
    """
    Computes the residual service curve (blind multiplexing) of a server with rate-latency strict service curve \\
    :math:`\\beta(t) = R(t-T)_+` crossed by a token-bucket arrival curve :math:`\\alpha = \\sigma + \\rho t`:\\
    :math:`\\beta_b(t) = (R-\\rho)( t - \\frac{TR + \\sigma}{R - \\rho})_+`

    :param rl: rate-latency service curve :math:`\\beta`
    :param tb: token-bucket arrival curve :math:`\\alpha`
    :return: a rate-latency service curve :math:`\\beta_b`


    >>> residual_blind(RateLatency(3, 4), TokenBucket(1, 2))
    1(t - 13.0)_+
    >>> residual_blind(RateLatency(2, 4), TokenBucket(1, 3))
    0(t - inf)_+
    >>> residual_blind(RateLatency(5, 4), TokenBucket(np.inf, 3))
    0(t - inf)_+
    """
    if tb.rho >= rl.rate or tb.sigma == np.inf:
        return RateLatency(0, np.inf)
    else:
        return RateLatency(rl.rate - tb.rho, (rl.latency * rl.rate + tb.sigma) / (rl.rate - tb.rho))


def residual_fifo(rl: RateLatency, tb: TokenBucket) -> RateLatency:
    """
    Computes a residual service curve (fifo multiplexing) of a server with rate-latency strict service curve \\
    :math:`\\beta(t) = R(t-T)_+` crossed by a token-bucket arrival curve :math:`\\alpha = \\sigma + \\rho t`:\\
    :math:`\\beta_f(t) = (R-\\rho)( t - \\frac{TR + \\sigma}{R})_+`

    :param rl: rate-latency service curve :math:`\\beta`
    :param tb: token-bucket arrival curve :math:`\\alpha`
    :return: a rate-latency service curve  :math:`\\beta_f`
    """
    if tb.rho >= rl.rate or tb.sigma == np.inf:
        return RateLatency(0, np.inf)
    else:
        return RateLatency(rl.rate - tb.rho, (rl.latency * rl.rate + tb.sigma) / rl.rate)


def output_arrival_curve(tb: TokenBucket, rl: RateLatency) -> TokenBucket:
    """Computes the arrival curve of the departure process of a single flow with token bucket arrival curve\\
    :math:`\\alpha = \\sigma + \\rho t`: crossing a single server with rate-latency service curve \\
    :math:`\\beta(t) = R(t-T)_+`:\\
    :math:`\\alpha_o(t) = \\sigma + \\rho T + \\rho t` (if :math:`R\\geq \\rho`)

    :param tb: the arrival curve of the arrival process :math:`\\alpha`
    :param rl: the service curve of the server :math:`\\beta`
    :return: token bucket function that is an arrival curve for the departure process: :math:`\\alpha_o`\\
        if :math:`R\\geq \\rho` and :math:`\\infty` otherwise.

    >>> output_arrival_curve(TokenBucket(3, 4), RateLatency(10, 2))
    11 + 4t
    >>> output_arrival_curve(TokenBucket(3, 4), RateLatency(3, 2))
    inf + inft
    """
    if rl.rate >= tb.rho:
        return TokenBucket(tb.sigma + tb.rho * rl.latency, tb.rho)
    else:
        return TokenBucket(np.inf, np.inf)


def rl_convolution(list_rl: List[RateLatency]) -> RateLatency:
    """
    Computes the (min, plus) convolution of a list of rate-latency functions \\
    :math:`\\beta_i(t) = R_i(t-T_i)_+`:
    :math:`\\beta(t) = \\beta_1 * \\cdots * \\beta_n(t) = (\\min_i R_i)  (t - \\sum_i T_i)`

    :param list_rl: list of rate latency functions :math:`\\beta_i`
    :return: the (min, plus) convolution of these functions :math:`\\beta`


    >>> rl_convolution([RateLatency(3, 4), RateLatency(6, 7), RateLatency(3, 2)])
    3(t - 13)_+
    >>> rl_convolution([])
    inf(t - 0)_+
    """
    if not list_rl:
        return RateLatency(np.inf, 0)
    latency = sum([rl.latency for rl in list_rl])
    rate = min([rl.rate for rl in list_rl])
    return RateLatency(rate, latency)


def intersection(rl: RateLatency, tb: TokenBucket) -> Tuple[float, float]:
    """
    Computes the intersection (not at 0) of a rate-latency  function :math:`\\beta_{R, T}` and a token-bucket curve\\
    :math:`\\gamma_{\\sigma, \\rho}`: Computes :math:`\\tau > 0` such that \\
    :math:`\\gamma_{\\sigma, \\rho}(\\tau) = \\beta_{R, T}(\\tau)`, that is \\
    :math:`\\tau = \\frac{\\sigma + RT}{R - \\rho}`, and $\\gamma_{\\sigma, \\rho}(\\tau)$.

    :param rl: rate latency function
    :type rl: RateLatency
    :param tb: token-bucket function
    :type tb: TokenBucket
    :return: the value :math:`\\tau` at which the functions intersect and the value of both function at :math:`\\tau``.
    """
    tau = (tb.sigma + rl.rate * rl.latency) / (rl.rate - tb.rho)
    return tau, tb.evaluate(tau)
