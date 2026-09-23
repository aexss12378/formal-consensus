from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from formal_consensus.workflows import run_all
from formal_consensus.workflows.pipeline import PipelineError


class RunAllTests(unittest.TestCase):
    def fake_pipeline(self, runs_dir: Path):
        return SimpleNamespace(
            problems={"p1": object(), "p2": object()},
            config=SimpleNamespace(runs_dir=runs_dir),
            run=mock.Mock(),
            lean_runner=mock.Mock(),
        )

    def run_main(self, pipeline, argv: list[str]):
        with (
            mock.patch.object(run_all, "build_pipeline", return_value=pipeline),
            mock.patch.object(
                run_all, "run_method_review", return_value=Path("review.json")
            ) as review,
            mock.patch.object(
                run_all,
                "run_representative_selection",
                return_value=Path("representatives.json"),
            ) as select,
            mock.patch.object(
                run_all,
                "build_report",
                return_value=(Path("report.json"), Path("report.md")),
            ) as report,
            mock.patch.object(
                run_all,
                "run_translation",
                return_value=(Path("translations.json"), Path("translations.md")),
            ) as translate,
            mock.patch.object(
                sys, "argv", ["run_all", "--input", "i", *argv]
            ),
            mock.patch("builtins.print"),
        ):
            run_all.main()
        return review, select, report, translate

    def test_all_steps_use_the_same_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.fake_pipeline(Path(tmp))
            review, select, report, translate = self.run_main(
                pipeline, ["--unit", "p1"]
            )
            run_dir = pipeline.run.call_args.args[1]
            self.assertEqual(pipeline.run.call_args.args[0], ["p1"])
            self.assertTrue(run_dir.is_dir())
            for step in (review, select, report):
                step.assert_called_once_with(run_dir)
            translate.assert_called_once_with(run_dir, Path("config.json"))
            pipeline.lean_runner.close.assert_called_once()

    def test_failure_tells_user_how_to_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.fake_pipeline(Path(tmp))
            pipeline.run.side_effect = PipelineError("API 中斷")
            with self.assertRaises(SystemExit) as caught:
                self.run_main(pipeline, [])
            self.assertEqual(pipeline.run.call_args.args[0], ["p1", "p2"])
            run_dir = pipeline.run.call_args.args[1]
            self.assertIn(f"--run-dir {run_dir}", str(caught.exception.code))
            pipeline.lean_runner.close.assert_called_once()

    def test_unknown_unit_does_not_create_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self.fake_pipeline(Path(tmp))
            with self.assertRaises(SystemExit):
                self.run_main(pipeline, ["--unit", "typo"])
            self.assertEqual(list(Path(tmp).iterdir()), [])
            pipeline.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
