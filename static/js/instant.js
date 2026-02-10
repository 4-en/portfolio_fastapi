
function instant_main() {

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
        } catch (e) {
            console.error(`[ERROR] Failed to preload: ${url}`);
        }
    }

    /**
     * Swap the content and update history
     */
    async function navigate(url) {
        let html = cache.get(url);
        
        if (!html) {
            console.warn(`[WARNING] No preloaded content for: ${url}, falling back to full page load.`);
            window.location.href = url;
            return;
        }

        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // 1. Update the Head (styles, meta, title)
        // updateHead(doc);

        // 2. Update the Content
        const newContent = doc.querySelector('html').innerHTML;
        const mainContainer = document.querySelector('html');

        // if either newContent or mainContainer is missing, fallback to full page load
        if (!newContent || !mainContainer) {
            window.location.href = url;
            console.warn(`[WARNING] Missing content for: ${url}, falling back to full page load.`);
            return;
        }



        mainContainer.innerHTML = newContent;

        // 3. Manually execute scripts in the new content
        executeScripts(mainContainer);

        // 4. History and Scroll
        document.title = doc.querySelector('title').innerText;
        window.history.pushState({ url }, document.title, url);
        window.scrollTo(0, 0);
        
        initLinks();
    }

    function executeScripts(container) {
        const scripts = container.querySelectorAll("script");
        scripts.forEach(oldScript => {
            const newScript = document.createElement("script");
            
            // Copy all attributes (src, type, etc.)
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });

            // Copy the inline code if there is no src
            newScript.appendChild(document.createTextNode(oldScript.innerHTML));
            
            // remove old script
            oldScript.parentNode.removeChild(oldScript);

            // Append the new script to the container
            container.appendChild(newScript);
        });
    }

    function updateHead(newDoc) {
        const currentHead = document.head;
        const newHead = newDoc.head;

        // This is a simple version: add things from newHead that aren't in currentHead
        // Better: use a library or a more complex diffing logic for CSS/Meta tags
        const newStyles = newHead.querySelectorAll('link[rel="stylesheet"], style');
        newStyles.forEach(style => {
            // Simple check to avoid duplicates (could be improved with href checks)
            currentHead.appendChild(style.cloneNode(true));
        });
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
}

if (document.DEF_INSTANTJS === undefined) {
    instant_main();
    document.DEF_INSTANTJS = true;
}