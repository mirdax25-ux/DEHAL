# Contributing

Contributions are welcome through pull requests.

1. Fork the repository.
2. Create a focused branch for your change.
3. Install the package and test dependencies, then run the test suite. Tests must pass before you open a pull request:

   ```bash
   python -m pip install -e ".[test]"
   python -m pytest
   ```

4. Open a pull request describing the change and its verification.

Use [Conventional Commits](https://www.conventionalcommits.org/) for commit messages, for example `docs: clarify v2 verification flow` or `feat: add evidence snapshot support`.
