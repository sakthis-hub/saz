# Library Management System (Frontend + Python Backend + MySQL)

  public/        Frontend: HTML, CSS, JavaScript (login + all pages)
  api/index.py   Backend: Python Flask API
  database/      library_db.sql (full MySQL database with sample data)
                 sample_data_cloud.sql (sample data for a cloud database)
  vercel.json, requirements.txt   Vercel settings

Logins (pick the matching user type):
  admin / admin123 = Librarian   asha / asha123 = Student   karthik / karthik123 = Member
(Without sample data, only admin / admin123 exists; it is created automatically.)

## A. Run on your computer (VS Code)
1. Install Python 3 and MySQL.
2. pip install -r requirements.txt
3. Optional sample data: mysql -u root -p < database/library_db.sql
4. Set your MySQL login, then start:
   Windows (cmd):  set DATABASE_URL=mysql://root:YOURPASSWORD@localhost:3306/library_db
   Mac/Linux:      export DATABASE_URL=mysql://root:YOURPASSWORD@localhost:3306/library_db
   python api/index.py
5. Open http://127.0.0.1:5000

## B. Deploy on Vercel
Vercel cannot host MySQL, so first create a free cloud MySQL database
(TiDB Cloud, Aiven, Railway...) and copy its connection details.
1. Push this folder to GitHub, then Vercel > Add New > Project > import it (framework: Other).
2. Settings > Environment Variables:
   SECRET_KEY    any long random text
   DATABASE_URL  mysql://USER:PASSWORD@HOST:PORT/DBNAME
   (special characters in the password must be URL-encoded: @ = %40, # = %23, : = %3A, / = %2F)
3. Deploy (or Redeploy after changing variables).
4. Open the link and log in. Tables and the admin account are created automatically.
5. Optional: run database/sample_data_cloud.sql once in your provider's SQL console.

If the login page shows "Database error: ...", the message says which setting is wrong.
