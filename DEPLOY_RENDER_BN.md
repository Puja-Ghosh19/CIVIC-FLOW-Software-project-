# CIVIC-FLOW: সম্পূর্ণ Flask Project Deploy (Render)

## গুরুত্বপূর্ণ
এই প্রজেক্টটি Flask server-rendered application। তাই শুধু Netlify-তে static publish করলে Login, Registration, Admin, Application Tracking ও MySQL কাজ করবে না। এই ZIP-এ Render-এর জন্য deployment entry point যোগ করা হয়েছে।

## 1. GitHub-এ আপডেট
1. ZIP extract করুন।
2. `CIVIC_FLOW` ফোল্ডারের ভেতরের সব ফাইল আপনার GitHub repository-র root-এ upload/commit করুন (অর্থাৎ `app.py`, `templates/`, `static/`, `requirements.txt`, `wsgi.py`, `render.yaml` root-এ থাকবে)।
3. `.env` বা কোনো password GitHub-এ upload করবেন না।

## 2. MySQL Database প্রস্তুত করুন
এই অ্যাপ MySQL + PyMySQL ব্যবহার করে। এমন একটি MySQL host/database নিন যেটি Render থেকে network connection allow করে। Database তৈরি করে নিচের তথ্য সংগ্রহ করুন:
- Host
- Port (সাধারণত 3306)
- Database name
- Username
- Password

`database_schema.sql`-এ database create করার sample আছে; অ্যাপ প্রথম start-এ প্রয়োজনীয় table তৈরি/upgrade করবে। Hosting provider অনুযায়ী database নিজে আগে তৈরি করতে হতে পারে।

## 3. Render-এ Web Service তৈরি
1. https://render.com/ এ GitHub দিয়ে sign in করুন।
2. New + → Blueprint নির্বাচন করুন (অথবা Web Service তৈরি করে একই settings দিন)।
3. আপনার repository connect করুন।
4. Render root-এ `render.yaml` পেলে Blueprint settings দেখাবে।
5. Deploy করার আগে Environment-এ DB_HOST, DB_USER, DB_PASSWORD, CIVIC_FLOW_ADMIN_EMAIL এবং CIVIC_FLOW_ADMIN_PASSWORD দিন। DB_NAME-ও আপনার database নাম অনুযায়ী ঠিক করুন।
6. `CIVIC_FLOW_ADMIN_PASSWORD`-এ শক্তিশালী unique password দিন; README-র demo password public deployment-এ ব্যবহার করবেন না।

## 4. Upload persistence
Render service-এ `render.yaml` একটি persistent disk (`/var/data`) নির্ধারণ করে। এই disk ব্যবহার করতে paid Starter instance প্রয়োজন হতে পারে এবং অতিরিক্ত charge প্রযোজ্য হতে পারে। Document upload যেন redeploy/restart-এর পরও থাকে, disk সক্রিয় রাখুন। খরচ এড়াতে free plan নিলে disk বাদ দিতে হবে—তখন redeploy/restart-এ uploaded files হারিয়ে যেতে পারে।

## 5. Deploy ও পরীক্ষা
Deploy সফল হলে Render একটি `https://....onrender.com` URL দেবে। পরীক্ষা করুন:
- `/` Homepage
- `/register` Registration
- `/login` Login
- `/services` Service list
- `/finder` Smart Finder
- `/admin` Admin dashboard (admin credentials দিয়ে)

নতুন database-এ প্রথম start-এ app table ও demo service seed করবে। DB connection ভুল হলে Render Logs-এ database connection error দেখুন।

## 6. Netlify সম্পর্কে
Netlify-তে static frontend publish করলে Flask routes server-side চলবে না। Netlify-only deployment করতে হলে Flask routes-কে আলাদা serverless functions/API-তে rewrite এবং database/file storage integration পরিবর্তন করতে হবে। বর্তমান পূর্ণ Flask app-এর জন্য Render এক-সার্ভিস deployment সহজতর।

## Security / limitations
- `CIVIC_FLOW_SECRET_KEY` অবশ্যই random secret রাখুন।
- Admin email/password Render Environment Variables-এ দিন।
- Database password GitHub-এ রাখবেন না।
- Uploaded files-এর জন্য persistent disk দরকার।
- এটি educational prototype; public launch-এর আগে security review, backup ও HTTPS/domain settings যাচাই করুন।
