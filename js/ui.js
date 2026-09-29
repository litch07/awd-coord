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
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-links .nav-link');
    const header = document.querySelector('.global-header');

    function updateScrollspy() {
        if (sections.length === 0 || navLinks.length === 0) return;
        
        // Use the middle of the viewport for detection
        const scrollPos = window.scrollY + (window.innerHeight / 2);

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
        window.addEventListener('resize', updateScrollspy, { passive: true });
        updateScrollspy();
    }

    // 4. Global Event Listeners
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn && typeof logout === 'function') {
        logoutBtn.addEventListener('click', logout);
    }

    // Mobile Menu Toggle
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mainNav = document.getElementById('main-nav');
    if (mobileMenuBtn && mainNav) {
        mobileMenuBtn.addEventListener('click', () => {
            mainNav.classList.toggle('show');
        });

        // Close menu when a navigation link is clicked on mobile
        mainNav.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    mainNav.classList.remove('show');
                }
            });
        });
    }
    // 5. Initialize Lucide Icons
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    // 6. Interactive Solution Flow Line
    const flowContainer = document.querySelector('.flow-steps');
    if (flowContainer) {
        const progressLine = flowContainer.querySelector('.flow-line-progress');
        const trackLine = flowContainer.querySelector('.flow-line-track');
        const stepCards = flowContainer.querySelectorAll('.step');

        const updateTrackBounds = () => {
            if (stepCards.length >= 2 && trackLine) {
                const firstCard = stepCards[0];
                const lastCard = stepCards[stepCards.length - 1];
                
                if (window.innerWidth >= 1024) {
                    // Horizontal (Desktop)
                    trackLine.style.top = '62px';
                    trackLine.style.height = '4px';
                    trackLine.style.bottom = 'auto';
                    
                    const firstCenter = firstCard.offsetLeft + (firstCard.offsetWidth / 2);
                    const lastCenter = lastCard.offsetLeft + (lastCard.offsetWidth / 2);
                    
                    trackLine.style.left = `${firstCenter}px`;
                    trackLine.style.width = `${lastCenter - firstCenter}px`;
                    if(progressLine) {
                        progressLine.classList.remove('vertical-gradient');
                        progressLine.style.height = '100%';
                    }
                } else {
                    // Vertical (Mobile/Tablet)
                    trackLine.style.left = '50%';
                    trackLine.style.width = '4px';
                    trackLine.style.transform = 'translateX(-50%)';
                    
                    // We connect the icon centers vertically
                    const firstIcon = firstCard.querySelector('.glow-icon');
                    const lastIcon = lastCard.querySelector('.glow-icon');
                    
                    const firstCenter = firstCard.offsetTop + (firstIcon ? firstIcon.offsetTop + (firstIcon.offsetHeight / 2) : 50);
                    const lastCenter = lastCard.offsetTop + (lastIcon ? lastIcon.offsetTop + (lastIcon.offsetHeight / 2) : lastCard.offsetHeight - 50);
                    
                    trackLine.style.top = `${firstCenter}px`;
                    trackLine.style.height = `${lastCenter - firstCenter}px`;
                    if(progressLine) {
                        progressLine.classList.add('vertical-gradient');
                        progressLine.style.width = '100%';
                    }
                }
            }
        };

        window.addEventListener('resize', updateTrackBounds, { passive: true });
        updateTrackBounds();
        setTimeout(updateTrackBounds, 250);

        stepCards.forEach((card, index) => {
            card.addEventListener('mouseenter', () => {
                // Update active step classes from 0 to index
                stepCards.forEach((c, i) => {
                    if (i <= index) {
                        c.classList.add('flow-active');
                    } else {
                        c.classList.remove('flow-active');
                    }
                });

                if (progressLine && stepCards.length > 1) {
                    const ratio = index / (stepCards.length - 1);
                    if (window.innerWidth >= 1024) {
                        progressLine.style.width = `${ratio * 100}%`;
                        progressLine.style.height = '100%';
                    } else {
                        progressLine.style.height = `${ratio * 100}%`;
                        progressLine.style.width = '100%';
                    }
                    progressLine.classList.add('active');
                }
            });
        });

        flowContainer.addEventListener('mouseleave', () => {
            stepCards.forEach(c => c.classList.remove('flow-active'));
            if (progressLine) {
                progressLine.style.width = '0%';
                progressLine.classList.remove('active');
            }
        });
    }
});
