"""`python -m formal_consensus` 等同執行 run_all；`... formalize` 起草 Lean 命題。"""

import sys

if __name__ == "__main__":
    if sys.argv[1:2] == ["formalize"]:
        from .workflows.formalize import main as formalize_main

        formalize_main(sys.argv[2:])
    else:
        from .workflows.run_all import main

        main()
