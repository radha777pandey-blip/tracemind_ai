const express = require('express');
const mysql = require('mysql2/promise');
const bcrypt = require('bcryptjs');
const path = require('path');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

const dbConfig = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'learnmate',
};

app.use(express.json());

// Serve landing page as home route (before static middleware)
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'landing.html'));
});

app.use(express.static(path.join(__dirname)));

async function getConnection() {
  return mysql.createConnection(dbConfig);
}

app.post('/api/signup', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) {
    return res.status(400).json({ success: false, message: 'Please fill all fields.' });
  }

  try {
    const hashedPassword = await bcrypt.hash(password, 10);
    const connection = await getConnection();
    const [existing] = await connection.execute('SELECT id FROM users WHERE email = ?', [email]);
    if (existing.length > 0) {
      await connection.end();
      return res.status(409).json({ success: false, message: 'Email already registered.' });
    }

    await connection.execute(
      'INSERT INTO users (full_name, email, password) VALUES (?, ?, ?)',
      [name, email, hashedPassword]
    );
    await connection.end();

    return res.json({ success: true, message: 'Account created successfully.' });
  } catch (error) {
    console.error(error);
    return res.status(500).json({ success: false, message: 'Server error while signing up.' });
  }
});

app.post('/api/signin', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ success: false, message: 'Please fill all fields.' });
  }

  try {
    const connection = await getConnection();
    const [rows] = await connection.execute(
      'SELECT id, full_name, password FROM users WHERE email = ?',
      [email]
    );
    await connection.end();
    if (rows.length === 0) {
      return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }

    const user = rows[0];
    const passwordMatches = await bcrypt.compare(password, user.password);
    if (!passwordMatches) {
      return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }

    return res.json({ success: true, message: 'Signed in successfully.' });
  } catch (error) {
    console.error(error);
    return res.status(500).json({ success: false, message: 'Server error while signing in.' });
  }
});

function getRecommendation(score, answers = []) {
  const total = 5;
  const percentage = Math.round((score / total) * 100);
  const recommendation = {
    score,
    total,
    percentage,
    path: 'Beginner Foundations',
    summary: 'Review core HTML, CSS and JavaScript concepts to build a stronger base before advancing.',
    nextSkill: 'HTML & CSS fundamentals',
    resources: [
      'HTML structure and semantics',
      'Responsive layout patterns',
      'JavaScript basics and control flow',
    ],
  };

  if (percentage >= 80) {
    recommendation.path = 'Advanced Frontend Developer';
    recommendation.summary = 'You are ready to master advanced frontend architecture, performance optimization, and modern component patterns.';
    recommendation.nextSkill = 'Advanced React Patterns';
    recommendation.resources = [
      'React performance optimization',
      'State management with Redux or Zustand',
      'Component design and reusable UI systems',
    ];
  } else if (percentage >= 50) {
    recommendation.path = 'Intermediate JavaScript Roadmap';
    recommendation.summary = 'Strengthen your JavaScript and modern frontend skills with intermediate patterns and practical application.';
    recommendation.nextSkill = 'JavaScript best practices';
    recommendation.resources = [
      'JavaScript ES6+ features',
      'React hooks and state management',
      'Modern CSS techniques',
    ];
  }

  const reactAnswerCorrect = answers[3] === 1;
  if (percentage >= 60 && reactAnswerCorrect) {
    recommendation.path = 'React Developer Track';
    recommendation.summary = 'Based on your quiz, focus on React development with hooks, component architecture, and modern UX patterns.';
    recommendation.nextSkill = 'React hooks and component state';
    recommendation.resources = [
      'React hooks deep dive',
      'Building reusable components',
      'Managing app state with context',
    ];
  }

  return recommendation;
}

app.post('/api/recommend', (req, res) => {
  const { score, answers } = req.body;
  if (typeof score !== 'number') {
    return res.status(400).json({ success: false, message: 'Score is required to generate a recommendation.' });
  }

  const recommendation = getRecommendation(score, Array.isArray(answers) ? answers : []);
  return res.json({ success: true, recommendation });
});

// Serve auth page
app.get('/auth', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard.html'));
});

app.get('/quiz', (req, res) => {
  res.sendFile(path.join(__dirname, 'quiz.html'));
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
