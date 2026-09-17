from __future__ import annotations

import unittest

from formal_consensus.workflows.method_review import aggregate_method_votes
from formal_consensus.workflows.representative_selection import (
    aggregate_selection_votes,
)


class PostprocessingTests(unittest.TestCase):
    @staticmethod
    def review(verdict: str):
        return {"review": {"verdict": verdict, "reason": "reason"}}

    @staticmethod
    def selection(candidate_id: str):
        return {"selection": {"candidate_id": candidate_id, "reason": "reason"}}

    def test_method_vote_rules_are_explicit(self) -> None:
        self.assertEqual(
            aggregate_method_votes(
                [self.review("pass"), self.review("pass"), self.review("fail")]
            ),
            "confirmed",
        )
        self.assertEqual(
            aggregate_method_votes(
                [self.review("fail"), self.review("fail"), self.review("pass")]
            ),
            "rejected",
        )
        self.assertEqual(
            aggregate_method_votes(
                [
                    self.review("pass"),
                    self.review("questionable"),
                    self.review("fail"),
                ]
            ),
            "unresolved",
        )

    def test_representative_requires_two_votes(self) -> None:
        self.assertEqual(
            aggregate_selection_votes(
                [
                    self.selection("A"),
                    self.selection("A"),
                    self.selection("B"),
                ]
            ),
            "A",
        )
        self.assertIsNone(
            aggregate_selection_votes(
                [
                    self.selection("A"),
                    self.selection("B"),
                    self.selection("C"),
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
