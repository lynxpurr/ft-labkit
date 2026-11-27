# Security and reporting

labkit is a local command-line tool, not a service or a sandbox. It executes
programs named by the project's `labkit.toml` (the training engine binary and
the training and reference interpreters), runs `git`, and reads and writes
files in the current project. Run it only in projects and environments you
trust, and do not run it inside an untrusted repository: its `labkit.toml`
can name any executable.

Use GitHub private vulnerability reporting when available for security issues.
For other problems, open an issue with a minimal input and package versions;
do not publish sensitive material in a report.
