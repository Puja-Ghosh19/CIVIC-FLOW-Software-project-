# CIVIC-FLOW — Smart Government Service Guide

CIVIC-FLOW is a student project that helps people explore common government-service guides, review general document requirements, and keep track of application records created inside this demo. The design uses soft, low-contrast colours and plain language to make the pages feel calmer and easier to follow.

## What you can do

- Create an account and sign in.
- Browse the service guides and search by service or department.
- Use Smart Finder to get a possible service match from a short description.
- Review the information shown for a service and submit a demo application.
- Check the reference number and status saved in CIVIC-FLOW.
- Use the admin page to add service guides and update demo application statuses.

## Technology

- Python and Flask for the web application
- HTML, CSS and JavaScript for the interface
- MySQL for persistent storage (PyMySQL connector)

## Run locally

1. Install Python and MySQL Server, and make sure MySQL is running.
2. Create a database named `civic_flow` in MySQL/phpMyAdmin.
3. Review `database_schema.sql` and execute it in the `civic_flow` database.
4. Copy `.env.example` to `.env` and set the database host, user, password and database name to match your computer.
5. Open a terminal in the folder that contains `app.py` and `requirements.txt`.
6. Install dependencies: `python -m pip install -r requirements.txt`
7. Start the app: `python app.py`
8. Open `http://127.0.0.1:5000` in your browser.

## Demo administrator

- Email: `admin@civicflow.com`
- Password: `admin123`

These are demo credentials only. Do not deploy the project publicly with the demo account or demo security settings.

## Important limitations

- Smart Finder uses simple keyword rules. It is not a trained machine-learning model.
- The processing-time value is a basic estimate, not a prediction learned from real historical records.
- Tracking displays the status saved in this app; it does not fetch live government-portal data.
- Fees, documents, and official procedures can change. Confirm them with the relevant authority.
- This is an educational prototype, not an official government service. Review authentication, password hashing, secret keys, input validation, and database permissions before any real deployment.


## Added feature: NID Application
CIVIC-FLOW now includes a separate **NID Application (New NID)** service guide alongside **NID Information Correction**. Users can open its details, review the checklist, submit an internal CIVIC-FLOW request, and track the generated reference. This is an internal project record only; it does not submit directly to the Election Commission portal. Use the official Election Commission process for the actual government application.
