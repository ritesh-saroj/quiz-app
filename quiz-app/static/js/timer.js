// Simple timer logic
document.addEventListener("DOMContentLoaded", function() {
    let timeLeft = 30; // 30 seconds per question
    const timerEl = document.getElementById("quiz-timer");
    
    if (timerEl) {
        const interval = setInterval(function() {
            timeLeft--;
            timerEl.textContent = `00:${timeLeft < 10 ? '0' : ''}${timeLeft}`;
            if (timeLeft <= 0) {
                clearInterval(interval);
                // Optionally auto-submit or handle timeout here.
            }
        }, 1000);
    }
});
