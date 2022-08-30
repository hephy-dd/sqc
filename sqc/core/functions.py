import logging
import time
from typing import Callable

import numpy as np
from scipy import stats

__all__ = ["steady_state_check"]

logger = logging.getLogger(__name__)


def steady_state_check(callback: Callable, *, n_iterations: int = 7,
                       n_samples: int = 4, max_slope: float = 0.001,
                       rsq: float = 0.95, waiting_time: float = 0.2,
                       waiting_time_factor: float = 1.0) -> bool:
    """Read values from a callback function and performs a linear fit on it. If the
    fit exceeds a maximum slope it waits a specified time and repeats. If the
    slope condition is not reached after a number of set attempts the function
    return False. Otherwise it return True and indicates a equilibrium has
    been reached.

    :param n_iterations: number of iterations
    :param n_samples: How many samples should be read from callback
    :param max_slope: The maximum slope, x-axis is measured in seconds, so a slope of 1e-9 is a change of 1n per second
    :param rsq: Minimum R^2 value
    :param waiting_time: How long to wait between attempts
    :param waiting_time_factor: factor the waiting time is increased with every iteration
    :return: True if steady state reached, else False
    """
    bad_fit: bool = False
    high_error: bool = False
    max_std_err: float = 1e-6
    std_err_factor: float = 2.5

    for iteration in range(n_iterations):
        counter: int = iteration + 1
        x = []
        y = []

        logger.debug("Conducting steady state check at iteration=%s...", counter)

        for i in range(n_samples):
            t0 = time.time()
            value = callback()
            t1 = time.time()
            dt = t1 - t0

            x.append(t1)
            y.append(value)

            if dt <= waiting_time:
                time.sleep(abs(dt - waiting_time))

        # Increase waiting time for next iteration
        waiting_time *= waiting_time_factor

        # Linear regression over time
        slope, intercept, r_value, p_value, std_err = stats.linregress(
            np.append([0], np.diff(x)), y
        )

        logger.debug("Slope parameters: slope=%e, intercept=%s, r^2=%e, std_err=%e", slope, intercept, (r_value * r_value), std_err)

        bad_fit = (r_value * r_value) < rsq
        high_error = (std_err * std_err_factor) > abs(slope)

        if std_err <= max_std_err and abs(slope) <= abs(max_slope):
            logger.debug("Steady state was reached with slope=%e at iteration=%d", slope, counter)
            if bad_fit:
                logger.debug("Steady state check yielded bad fit conditions. Results may be compromised! R^2=%e at iteration=%d", (r_value * r_value), counter)
            high_error_slope = abs(slope) + std_err_factor * std_err > abs(max_slope)
            # If fit errors are high, the 2.5x the error is bigger as the slope and 0.5% of the maximum_error_slope is bigger as the actuall value
            if (high_error and high_error_slope and abs(slope) + std_err_factor * std_err > abs(intercept)):
                logger.warning("Steady state check yielded high fit error conditions. Results may be compromised! std_err=%e at iteration=%d", std_err, counter)
            return True

        logger.debug("Steady state was not reached due to high error and steep slope after %d iterations", counter)

    logger.info("Attempt to reach steady state was not successfully after %d iterations", n_iterations)
    return False
