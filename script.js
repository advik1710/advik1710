document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.card');
    const buttons = document.querySelectorAll('.btn');
    const title = document.getElementById('main-title');

    // 1. Interactive 3D Card Hover & Border Glow Effect
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = (y - centerY) / 20;
            const rotateY = (centerX - x) / 20;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-4px)`;
            card.style.borderColor = '#38bdf8';
            card.style.boxShadow = `0 12px 30px rgba(56, 189, 248, 0.15)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0px)';
            card.style.borderColor = '#334155';
            card.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)';
        });
    });

    // 2. Button Ripple Effect on Click
    buttons.forEach(button => {
        button.addEventListener('click', function (e) {
            const circle = document.createElement('span');
            const diameter = Math.max(this.clientWidth, this.clientHeight);
            const radius = diameter / 2;

            const rect = this.getBoundingClientRect();
            circle.style.width = circle.style.height = `${diameter}px`;
            circle.style.left = `${e.clientX - rect.left - radius}px`;
            circle.style.top = `${e.clientY - rect.top - radius}px`;
            circle.style.position = 'absolute';
            circle.style.borderRadius = '50%';
            circle.style.background = 'rgba(255, 255, 255, 0.35)';
            circle.style.transform = 'scale(0)';
            circle.style.animation = 'ripple 0.6s linear';
            circle.style.pointerEvents = 'none';

            const existingRipple = this.querySelector('span');
            if (existingRipple) {
                existingRipple.remove();
            }

            this.appendChild(circle);
        });
    });

    // 3. Header Scale Animation on Hover
    if (title) {
        title.addEventListener('mouseenter', () => {
            title.style.transform = 'scale(1.05)';
        });
        title.addEventListener('mouseleave', () => {
            title.style.transform = 'scale(1)';
        });
    }
});

// Inject keyframe stylesheet for button ripple
const style = document.createElement('style');
style.innerHTML = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
