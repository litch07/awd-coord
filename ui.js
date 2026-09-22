// ui.js - Global User Interface behaviors

document.addEventListener('DOMContentLoaded', () => {
    // 1. Fade-In Animation Observer
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.fade-in-up').forEach(el => {
        el.style.animationPlayState = 'paused';
        observer.observe(el);
    });

    // 2. Auth State UI Update (Nav Buttons)
    if (typeof isAuthenticated === 'function' && isAuthenticated()) {
        const btnContainer = document.querySelector('.nav-auth-buttons');
        if (btnContainer) {
            btnContainer.innerHTML = '<a href="dashboard.html" class="btn btn-primary btn-sm">Dashboard</a>';
        }
    }

    // 3. Scrollspy Implementation (For Landing Page)
    const sections = document.querySelectorAll('main section[id]');
    const navLinks = document.querySelectorAll('.nav-links .nav-link');
    const header = document.querySelector('.global-header');

    function updateScrollspy() {
        if (sections.length === 0 || navLinks.length === 0) return;
        
        const headerHeight = header ? header.offsetHeight : 70;
        const scrollPos = window.scrollY + headerHeight + 80;

        let activeSectionId = '';

        sections.forEach(section => {
            const top = section.offsetTop;
            const height = section.offsetHeight;
            if (scrollPos >= top && scrollPos < top + height) {
                activeSectionId = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href === `#${activeSectionId}`) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    if (sections.length > 0) {
        window.addEventListener('scroll', updateScrollspy, { passive: true });
        updateScrollspy();
    }

    // 4. Global Event Listeners
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn && typeof logout === 'function') {
        logoutBtn.addEventListener('click', logout);
    }
    // 5. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});
