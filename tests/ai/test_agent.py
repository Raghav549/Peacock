import unittest

from peacock.intelligence.agent import Agent, AgentError


class AgentPlanningTests(unittest.TestCase):
    def make_agent(self):
        agent = Agent("location", "home", 8)
        agent.fact("location", "outside")
        agent.rule("location", "outside", "walk door", "location", "door", priority=5, cost=2)
        agent.rule("location", "door", "enter home", "location", "home", priority=5, cost=1)
        agent.rule("location", "outside", "walk garden", "location", "garden", priority=9, cost=10)
        return agent

    def test_minimum_cost_plan_ignores_salience_for_cost(self):
        self.assertEqual(self.make_agent().plan(), ["walk door", "enter home"])

    def test_run_updates_blackboard_and_trace(self):
        agent = self.make_agent()
        self.assertEqual(agent.run(), ["walk door", "enter home"])
        self.assertEqual(agent.get("location"), "home")
        self.assertEqual(agent.status, "succeeded")
        self.assertEqual(len(agent.trace()), 2)
        self.assertIn("location=home", agent.fact_lines())

    def test_goal_already_satisfied(self):
        agent = Agent("location", "home")
        agent.fact("location", "home")
        self.assertEqual(agent.plan(), [])
        self.assertEqual(agent.run(), [])
        self.assertEqual(agent.status, "succeeded")

    def test_unreachable_goal_is_bounded_stall(self):
        agent = Agent("location", "home")
        agent.fact("location", "outside")
        self.assertIsNone(agent.plan())
        self.assertEqual(agent.run(), [])
        self.assertEqual(agent.status, "stalled")

    def test_step_limit(self):
        agent = Agent("state", "c", 1)
        agent.fact("state", "a")
        agent.rule("state", "a", "a to b", "state", "b")
        agent.rule("state", "b", "b to c", "state", "c")
        self.assertIsNone(agent.plan())

    def test_priority_breaks_equal_cost_ties(self):
        agent = Agent("state", "goal")
        agent.fact("state", "start")
        agent.rule("state", "start", "low", "state", "goal", priority=1)
        agent.rule("state", "start", "high", "state", "goal", priority=10)
        self.assertEqual(agent.plan(), ["high"])

    def test_rule_and_fact_validation(self):
        agent = Agent("state", "goal")
        with self.assertRaises(AgentError):
            agent.rule("state", "start", "bad", "state", "goal", cost=0)
        with self.assertRaises(AgentError):
            agent.get("missing")
        with self.assertRaises(AgentError):
            Agent("state", "goal", 0)


if __name__ == "__main__":
    unittest.main()
