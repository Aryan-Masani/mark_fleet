"""
moqpso.py — Multi-Objective Quantum-Inspired Particle Swarm Optimization (MOQPSO).
Subclasses jMetalPy's SMPSO, reusing its CrowdingDistanceArchive, DominanceComparator,
and select_global_best() leader tournament selection, while overriding position/velocity
mechanics with the standard Mean-Best (mbest) quantum-behaved update rule.
"""

from __future__ import annotations
import copy
import random
from typing import Callable, List, Optional
import numpy as np

from jmetal.algorithm.multiobjective.smpso import SMPSO
from jmetal.core.operator import Mutation
from jmetal.core.problem import FloatProblem
from jmetal.core.solution import FloatSolution
from jmetal.operator.mutation import PolynomialMutation
from jmetal.util.archive import BoundedArchive, CrowdingDistanceArchive
from jmetal.util.comparator import Comparator, DominanceComparator
from jmetal.util.termination_criterion import StoppingByEvaluations, TerminationCriterion


class MOQPSO(SMPSO):
    """
    Multi-Objective Quantum-Behaved Particle Swarm Optimization (MOQPSO).

    Key features:
    - Zero velocity vector (QPSO position update replaces velocity mechanics).
    - Swarm mean-best position (mbest) across all particle local bests.
    - Contraction-expansion coefficient beta(t) linearly annealed from beta_max to beta_min.
    - Stochastic attractor p_id and quantum delta-potential-well sampling:
        x_id <- p_id +/- 2 * beta(t) * |mbest_d - x_id| * ln(1/u)
    - Reuses jMetalPy SMPSO leader archive, dominance comparator, and light mutation perturbation.
    """

    def __init__(
        self,
        problem: FloatProblem,
        swarm_size: int = 50,
        max_evaluations: int = 2500,
        beta_max: float = 1.0,
        beta_min: float = 0.4,
        mutation: Optional[Mutation] = None,
        leaders: Optional[BoundedArchive] = None,
        dominance_comparator: Comparator = DominanceComparator(),
        step_callback: Optional[Callable[[int, int, List[FloatSolution]], None]] = None,
    ):
        if leaders is None:
            leaders = CrowdingDistanceArchive(maximum_size=100, dominance_comparator=dominance_comparator)

        if mutation is None:
            prob = 1.0 / max(1, problem.number_of_variables())
            mutation = PolynomialMutation(probability=prob, distribution_index=20.0)

        termination_criterion = StoppingByEvaluations(max_evaluations=max_evaluations)

        super().__init__(
            problem=problem,
            swarm_size=swarm_size,
            mutation=mutation,
            leaders=leaders,
            dominance_comparator=dominance_comparator,
            termination_criterion=termination_criterion,
        )

        self.max_evaluations = max_evaluations
        self.beta_max = beta_max
        self.beta_min = beta_min
        self.step_callback = step_callback

        # Cache problem bounds as numpy arrays
        self.lower_bounds_arr = np.asarray(problem.lower_bound, dtype=float)
        self.upper_bounds_arr = np.asarray(problem.upper_bound, dtype=float)
        self.num_vars = problem.number_of_variables()

    def get_name(self) -> str:
        return "MOQPSO"

    def update_velocity(self, swarm: List[FloatSolution]) -> None:
        """No-op: QPSO has no velocity vector."""
        pass

    def update_position(self, swarm: List[FloatSolution]) -> None:
        """
        Quantum position update using the standard mbest formulation:
        1. mbest_d = mean over swarm of each particle's local_best_d
        2. beta(t) linearly annealed from beta_max to beta_min
        3. For each particle i and dimension d:
           phi, u ~ U(0, 1)
           p_id = phi * pbest_id + (1 - phi) * gbest_d
           L_id = 2 * beta(t) * |mbest_d - x_id|
           x_id <- p_id +/- L_id * ln(1 / u)
        """
        # Calculate search progress in [0, 1]
        progress = min(1.0, float(self.evaluations) / float(max(1, self.max_evaluations)))
        beta = self.beta_max - progress * (self.beta_max - self.beta_min)

        # Notify problem for annealed penalty coefficient if supported
        if hasattr(self.problem, "set_annealed_lambda"):
            self.problem.set_annealed_lambda(progress)

        # Compute mbest across all particles' local bests: shape (D,)
        local_bests = np.array([p.attributes["local_best"].variables for p in swarm], dtype=float)
        mbest = np.mean(local_bests, axis=0)

        # Update each particle
        for i in range(self.swarm_size):
            particle = swarm[i]
            x_i = np.asarray(particle.variables, dtype=float)
            pbest_i = np.asarray(particle.attributes["local_best"].variables, dtype=float)

            # Global best selected from leader archive via SMPSO's binary tournament
            gbest = self.select_global_best()
            gbest_vars = np.asarray(gbest.variables, dtype=float)

            # Fresh random draws per dimension
            phi = np.random.uniform(0.0, 1.0, size=self.num_vars)
            # Guard against u = 0.0 for log
            u = np.random.uniform(1e-12, 1.0, size=self.num_vars)
            signs = np.where(np.random.rand(self.num_vars) > 0.5, 1.0, -1.0)

            # Local stochastic attractor
            p_id = phi * pbest_i + (1.0 - phi) * gbest_vars

            # Characteristic quantum length
            l_id = 2.0 * beta * np.abs(mbest - x_i)

            # Quantum position update
            new_pos = p_id + signs * l_id * np.log(1.0 / u)

            # Clip to problem bounds
            clipped_pos = np.clip(new_pos, self.lower_bounds_arr, self.upper_bounds_arr)
            particle.variables = clipped_pos.tolist()

    def step(self) -> None:
        """Executes one optimization iteration with optional callback invocation."""
        super().step()
        if self.step_callback is not None:
            self.step_callback(self.evaluations, self.max_evaluations, self.leaders.solution_list)

    def get_pareto_front(self) -> List[FloatSolution]:
        """Returns the non-dominated Pareto archive solutions."""
        return self.result()
