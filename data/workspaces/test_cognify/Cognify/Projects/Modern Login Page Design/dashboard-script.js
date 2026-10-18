document.addEventListener('DOMContentLoaded', () => {
    const navToggle = document.querySelector('.nav-toggle');
    const dashboardNav = document.querySelector('.dashboard-nav');

    if (navToggle && dashboardNav) {
        navToggle.addEventListener('click', () => {
            dashboardNav.classList.toggle('open');
        });
    }

    const sections = document.querySelectorAll('.overview-card, .panel, .activity-card, .resource-item');
    const observerOptions = {
        threshold: 0.12,
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal-visible');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    sections.forEach((section) => {
        section.classList.add('reveal-hidden');
        observer.observe(section);
    });

    const greeting = document.querySelector('.eyebrow');
    if (greeting) {
        const hour = new Date().getHours();
        let timeOfDay = 'Learner';
        if (hour >= 5 && hour < 12) timeOfDay = 'Morning';
        else if (hour >= 12 && hour < 17) timeOfDay = 'Afternoon';
        else if (hour >= 17) timeOfDay = 'Evening';
        greeting.textContent = `Good ${timeOfDay}, Learner`;
    }

    loadRecommendation();
});

function loadRecommendation() {
    const stored = localStorage.getItem('cognifyRecommendation');
    if (!stored) {
        return;
    }

    try {
        const recommendation = JSON.parse(stored);
        const recommendedPath = document.getElementById('dashboardRecommendedPath');
        const nextSkill = document.getElementById('dashboardNextSkill');
        const summary = document.getElementById('dashboardRecommendationSummary');

        if (recommendedPath && recommendation.path) {
            recommendedPath.textContent = recommendation.path;
        }
        if (nextSkill && recommendation.nextSkill) {
            nextSkill.textContent = recommendation.nextSkill;
        }
        if (summary && recommendation.summary) {
            summary.textContent = recommendation.summary;
        }
    } catch (error) {
        console.error('Failed to parse recommendation data:', error);
    }
}

const style = document.createElement('style');
style.textContent = `
.reveal-hidden {
    opacity: 0;
    transform: translateY(20px);
    transition: transform 0.8s ease, opacity 0.8s ease;
}

.reveal-visible {
    opacity: 1;
    transform: translateY(0);
}

.dashboard-nav.open {
    display: flex;
    flex-direction: column;
    width: 100%;
    gap: 14px;
    margin-top: 16px;
}
`;
document.head.appendChild(style);
