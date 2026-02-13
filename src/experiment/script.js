const pupils = document.querySelectorAll('.pupil');
const eyes = document.querySelectorAll('.eye');

// 1. Randomly move pupils
const movePupils = () => {
    pupils.forEach(pupil => {
        const randomX = Math.floor(Math.random() * 3); // 0, 1, or 2
        let transform;

        switch (randomX) {
            case 0: // Left
                transform = 'translate(-100%, -50%)';
                break;
            case 1: // Right
                transform = 'translate(0%, -50%)';
                break;
            default: // Center
                transform = 'translate(-50%, -50%)';
                break;
        }
        pupil.style.transform = transform;
    });
};

setInterval(movePupils, 2000); // Move every 2 seconds

// 2. Add random blinking
function blink() {
    eyes.forEach(eye => {
        // Ensure the correct transform is applied during blink
        const currentTransform = window.getComputedStyle(eye).transform;
        
        eye.classList.add('blink');
        
        setTimeout(() => {
            eye.classList.remove('blink');
        }, 400);
    });
}

setInterval(() => {
    blink();
}, Math.random() * 5000 + 2000); // Blink every 2-7 seconds