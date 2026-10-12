
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(100),
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','member','librarian') NOT NULL DEFAULT 'student',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  author VARCHAR(120) NOT NULL,
  isbn VARCHAR(20) UNIQUE,
  category VARCHAR(60),
  total_copies INT NOT NULL DEFAULT 1,
  available_copies INT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS issues (
  id INT AUTO_INCREMENT PRIMARY KEY,
  book_id INT NOT NULL,
  user_id INT NOT NULL,
  issue_date DATE NOT NULL,
  due_date DATE NOT NULL,
  return_date DATE NULL,
  FOREIGN KEY (book_id) REFERENCES books(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);


-- Sample accounts: admin/admin123 (librarian), asha/asha123 (student), karthik/karthik123 (member)
INSERT IGNORE INTO users (full_name, username, email, password_hash, role) VALUES
('Head Librarian','admin','admin@library.local','scrypt:32768:8:1$kUojJdJmF14uUGUX$ca53d981eb027de75c6203d343a2635ee88f9403848170e82c630cbfcf64d60c389fe68eaac6f916ae2af540314c24231620f8a75a60d1d458fffc8e324c93a1','librarian'),
('Asha Raman','asha','asha@library.local','scrypt:32768:8:1$7tEprVSDpFODmNLG$231cf6f4a5d4cea6c1bb603dc6305d65bc2e0cd118d67796ae6053016d5416f7170d8b4bdc9c09be6846d23f577607c861ee79dd47d5cee8a0345a830b6d2879','student'),
('Karthik S','karthik','karthik@library.local','scrypt:32768:8:1$BmxZQ7eWppHCu0Hc$4658d1d7412e13357186935286a69733ec143020e90355d68cf780a90ce83678d79d46a4b3c95f4006c3cd5361a89bc252e2a767fba73637cdda2c86e163c793','member');

INSERT IGNORE INTO books (title, author, isbn, category, total_copies, available_copies) VALUES
('Wings of Fire','A. P. J. Abdul Kalam','LMS-0001','Biography',3,2),
('The Alchemist','Paulo Coelho','LMS-0002','Fiction',2,2),
('Introduction to Algorithms','Thomas H. Cormen','LMS-0003','Computer Science',2,1),
('Sapiens','Yuval Noah Harari','LMS-0004','History',1,0),
('Clean Code','Robert C. Martin','LMS-0005','Computer Science',2,2),
('Ponniyin Selvan','Kalki Krishnamurthy','LMS-0006','Fiction',2,2);

-- Run this file once. Loans are looked up by username / ISBN, so ids don't matter.
INSERT INTO issues (book_id, user_id, issue_date, due_date)
SELECT b.id, u.id, CURDATE() - INTERVAL 20 DAY, CURDATE() - INTERVAL 6 DAY FROM books b, users u WHERE b.isbn='LMS-0001' AND u.username='asha';
INSERT INTO issues (book_id, user_id, issue_date, due_date)
SELECT b.id, u.id, CURDATE() - INTERVAL 3 DAY, CURDATE() + INTERVAL 11 DAY FROM books b, users u WHERE b.isbn='LMS-0003' AND u.username='karthik';
INSERT INTO issues (book_id, user_id, issue_date, due_date)
SELECT b.id, u.id, CURDATE() - INTERVAL 2 DAY, CURDATE() + INTERVAL 12 DAY FROM books b, users u WHERE b.isbn='LMS-0004' AND u.username='asha';
