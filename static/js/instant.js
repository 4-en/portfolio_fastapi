const cache = new Map();

/**
 * Fetch and store the page content
 */
async function preload(url) {
    if (cache.has(url) || url.includes('#')) return;
    
    try {
        const res = await fetch(url);
        const html = await res.text();
        cache.set(url, html);
        console.log(`[SYSTEM] Preloaded: ${url}`);
    } catch (e) {
        console.error(`[ERROR] Failed to preload: ${url}`);
    }
}

/**
 * Swap the content and update history
 */
async function navigate(url) {
    let html = cache.get(url);
    
    // If not in cache (user clicked too fast), fetch it now
    if (!html) {
        const res = await fetch(url);
        html = await res.text();
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const newContent = doc.querySelector('main').innerHTML;
    const newTitle = doc.querySelector('title').innerText;

    // Update the DOM
    document.querySelector('main').innerHTML = newContent;
    document.title = newTitle;
    window.history.pushState({ url }, newTitle, url);
    
    // Re-scroll to top
    window.scrollTo(0, 0);
    
    // Re-bind listeners for new links in the swapped content
    initLinks();
}

function initLinks() {

    // disable for mobile devices (where hover doesn't exist and preloading can be more expensive)
    if (/Mobi|Android/i.test(navigator.userAgent)) return;

    document.querySelectorAll('a').forEach(link => {
        const url = link.href;

        if (!url) return;
        if (url.startsWith('mailto:') || url.startsWith('tel:')) return;
        if (url.startsWith('http') && !url.startsWith(window.location.origin)) return;
        if (url.includes('#')) return;
        if (url.includes('javascript:')) return;
        if (url.includes('/admin')) return; // Skip admin links


        // Only handle internal links
        if (url.startsWith(window.location.origin) && !url.includes('#')) {
            
            // 1. Preload on hover
            link.addEventListener('mouseenter', () => preload(url), { once: true });

            // 2. Instant swap on click
            link.addEventListener('click', (e) => {
                e.preventDefault();
                navigate(url);
            });
        }
    });
}

// Handle browser back/forward buttons
window.addEventListener('popstate', () => location.reload());

// Initial run
document.addEventListener('DOMContentLoaded', initLinks);