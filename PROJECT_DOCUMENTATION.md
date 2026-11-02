# CIVIC-FLOW — Project Notes

## Purpose
CIVIC-FLOW is an educational prototype intended to make public-service information easier to browse. It provides a simple starting point, not an official decision or replacement for government offices.

## Main user flow
1. A visitor browses service guides or describes a need in Smart Finder.
2. The app suggests a service using keyword rules.
3. A registered user can create an application record for a listed service.
4. The app assigns a reference number and stores the record in MySQL.
5. The user can view the latest status saved in the app.
6. An administrator can add service guides and update application statuses.

## Design approach
The interface uses a muted teal, mist-blue, lavender and warm-neutral palette, rounded cards, clear headings, responsive layouts and plain-language prompts. The goal is to make the project feel welcoming without hiding important limitations.

## Data and limitations
The database schema is in `database_schema.sql`. Smart Finder is rule-based and the processing-time helper is a simple baseline. Application tracking is internal to this prototype; it is not connected to a live government portal. Information about fees and documents should be checked with the relevant authority.

## Before real-world use
This code is for learning and demonstration. Add secure password hashing, environment-managed secret keys, stronger validation, authorization checks, logging and tests before deployment. Never use real citizen identity documents or sensitive personal information in a classroom demo.


## Added feature: NID Application
CIVIC-FLOW now includes a separate **NID Application (New NID)** service guide alongside **NID Information Correction**. Users can open its details, review the checklist, submit an internal CIVIC-FLOW request, and track the generated reference. This is an internal project record only; it does not submit directly to the Election Commission portal. Use the official Election Commission process for the actual government application.
