# How to run the CIVIC-FLOW tests

No MySQL or XAMPP is needed. The tests use an in-memory SQLite database.

```
pip install -r requirements.txt coverage
python -m unittest discover -s tests -t . -v
coverage run --branch --source=app,ai -m unittest discover -s tests -t .
coverage report -m
```

Test files: `tests/test_auth.py`, `tests/test_finder.py`, `tests/test_services_upload.py`, `tests/test_apply_tracking.py`.
Test case IDs (TC-xx) in the test names match the Requirements Traceability Matrix in the Test Report.
