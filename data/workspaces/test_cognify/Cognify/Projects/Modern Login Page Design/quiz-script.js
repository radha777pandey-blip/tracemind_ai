const quizData = [
  {
    question: 'Which HTML element is used to define the most important heading on a page?',
    options: ['<heading>', '<h1>', '<title>', '<header>'],
    answer: 1,
  },
  {
    question: 'Which CSS property controls the space between lines of text?',
    options: ['line-height', 'letter-spacing', 'text-spacing', 'word-spacing'],
    answer: 0,
  },
  {
    question: 'What does the JavaScript method Array.prototype.map() return?',
    options: ['A new array', 'A boolean', 'The original array', 'Undefined'],
    answer: 0,
  },
  {
    question: 'Which React hook is used for managing state inside a functional component?',
    options: ['useEffect()', 'useState()', 'useMemo()', 'useCallback()'],
    answer: 1,
  },
  {
    question: 'What does async/await help you handle more easily in JavaScript?',
    options: ['Form validation', 'DOM manipulation', 'Asynchronous code', 'CSS transitions'],
    answer: 2,
  },
];

const state = {
  currentQuestionIndex: 0,
  answers: new Array(quizData.length).fill(null),
};

const questionTitle = document.getElementById('questionTitle');
const choicesContainer = document.getElementById('choices');
const quizProgressLabel = document.getElementById('quizProgressLabel');
const quizProgressBar = document.getElementById('quizProgressBar');
const prevButton = document.getElementById('prevButton');
const nextButton = document.getElementById('nextButton');
const resetQuiz = document.getElementById('resetQuiz');
const resultsPanel = document.getElementById('resultsPanel');
const finalScore = document.getElementById('finalScore');
const finalPercentage = document.getElementById('finalPercentage');
const recommendedPath = document.getElementById('recommendedPath');
const recommendationText = document.getElementById('recommendationText');
const recommendedResources = document.getElementById('recommendedResources');
const reviewAnswers = document.getElementById('reviewAnswers');

function renderQuestion() {
  const currentIndex = state.currentQuestionIndex;
  const question = quizData[currentIndex];

  questionTitle.textContent = question.question;
  quizProgressLabel.textContent = `Question ${currentIndex + 1} of ${quizData.length}`;
  quizProgressBar.style.width = `${((currentIndex + 1) / quizData.length) * 100}%`;

  choicesContainer.innerHTML = '';

  question.options.forEach((option, index) => {
    const choiceElement = document.createElement('label');
    choiceElement.className = 'choice';

    const radioInput = document.createElement('input');
    radioInput.type = 'radio';
    radioInput.name = 'quizChoice';
    radioInput.value = index;
    radioInput.checked = state.answers[currentIndex] === index;

    radioInput.addEventListener('change', () => {
      state.answers[currentIndex] = index;
    });

    const optionText = document.createElement('span');
    optionText.textContent = option;

    choiceElement.appendChild(radioInput);
    choiceElement.appendChild(optionText);
    choicesContainer.appendChild(choiceElement);
  });

  prevButton.disabled = currentIndex === 0;
  nextButton.textContent = currentIndex === quizData.length - 1 ? 'Finish' : 'Next';
}

function calculateResults() {
  const correctAnswers = state.answers.reduce((score, selected, index) => {
    if (selected === quizData[index].answer) {
      return score + 1;
    }
    return score;
  }, 0);

  return {
    score: correctAnswers,
    percentage: Math.round((correctAnswers / quizData.length) * 100),
  };
}

async function requestRecommendation(results) {
  try {
    const response = await fetch('/api/recommend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        score: results.score,
        answers: state.answers,
      }),
    });

    if (!response.ok) {
      throw new Error('Unable to fetch recommendation');
    }

    const payload = await response.json();
    return payload.recommendation || {
      path: 'Frontend Developer',
      summary: 'Keep practicing and improve your fundamentals.',
      nextSkill: 'JavaScript fundamentals',
      resources: ['HTML basics', 'CSS layout', 'JavaScript syntax'],
    };
  } catch (error) {
    console.error(error);
    return {
      path: 'Frontend Developer',
      summary: 'Keep practicing and improve your fundamentals.',
      nextSkill: 'JavaScript fundamentals',
      resources: ['HTML basics', 'CSS layout', 'JavaScript syntax'],
    };
  }
}

function renderRecommendation(recommendation, results) {
  finalScore.textContent = `${results.score}/${quizData.length}`;
  finalPercentage.textContent = `${results.percentage}%`;
  recommendedPath.textContent = recommendation.path;
  recommendationText.textContent = recommendation.summary;

  recommendedResources.innerHTML = recommendation.resources
    .map((resource) => `<li>${resource}</li>`)
    .join('');

  localStorage.setItem('cognifyRecommendation', JSON.stringify({
    ...recommendation,
    score: results.score,
    percentage: results.percentage,
    total: quizData.length,
  }));

  resultsPanel.classList.remove('hidden');
}

function hideResults() {
  resultsPanel.classList.add('hidden');
}

async function completeQuiz() {
  const allAnswered = state.answers.every((answer) => answer !== null);
  if (!allAnswered) {
    alert('Please answer all questions before finishing the quiz.');
    return;
  }

  const results = calculateResults();
  const recommendation = await requestRecommendation(results);
  renderRecommendation(recommendation, results);
}

nextButton.addEventListener('click', async () => {
  if (state.currentQuestionIndex === quizData.length - 1) {
    await completeQuiz();
    return;
  }

  state.currentQuestionIndex += 1;
  hideResults();
  renderQuestion();
});

prevButton.addEventListener('click', () => {
  if (state.currentQuestionIndex === 0) {
    return;
  }
  state.currentQuestionIndex -= 1;
  hideResults();
  renderQuestion();
});

resetQuiz.addEventListener('click', () => {
  state.currentQuestionIndex = 0;
  state.answers = new Array(quizData.length).fill(null);
  hideResults();
  renderQuestion();
});

reviewAnswers.addEventListener('click', (event) => {
  event.preventDefault();
  state.currentQuestionIndex = 0;
  hideResults();
  renderQuestion();
});

window.addEventListener('load', () => {
  renderQuestion();
});
