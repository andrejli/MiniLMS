// Security utilities for XSS protection

/**
 * Escape HTML entities to prevent XSS attacks
 * @param {string} unsafe - Untrusted user input
 * @returns {string} - Sanitized string safe for HTML insertion
 */
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') {
        return String(unsafe);
    }
    
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    };
    
    return unsafe.replace(/[&<>"'/]/g, char => map[char]);
}

/**
 * Sanitize URL to prevent javascript: protocol
 * @param {string} url - URL to sanitize
 * @returns {string} - Safe URL or empty string
 */
function sanitizeUrl(url) {
    if (!url) return '';
    
    const trimmed = url.trim().toLowerCase();
    
    // Block dangerous protocols
    const dangerousProtocols = ['javascript:', 'data:', 'vbscript:', 'file:'];
    
    for (const protocol of dangerousProtocols) {
        if (trimmed.startsWith(protocol)) {
            console.warn('Blocked dangerous URL protocol:', url);
            return '';
        }
    }
    
    return url;
}

/**
 * Create text node safely
 * @param {string} text - Text content
 * @returns {Text} - DOM text node
 */
function createTextNode(text) {
    return document.createTextNode(String(text));
}

/**
 * Create element with safe text content
 * @param {string} tagName - HTML tag name
 * @param {string} textContent - Text content (will be escaped)
 * @param {Object} attributes - Element attributes
 * @returns {HTMLElement} - Created element
 */
function createElement(tagName, textContent = '', attributes = {}) {
    const element = document.createElement(tagName);
    
    if (textContent) {
        element.textContent = textContent; // Automatically escapes
    }
    
    // Set attributes safely
    for (const [key, value] of Object.entries(attributes)) {
        if (key === 'href' || key === 'src') {
            element.setAttribute(key, sanitizeUrl(value));
        } else if (key.startsWith('on')) {
            // Never allow event handler attributes
            console.warn('Blocked event handler attribute:', key);
        } else {
            element.setAttribute(key, value);
        }
    }
    
    return element;
}

/**
 * Validate and sanitize number
 * @param {*} value - Value to validate
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @returns {number} - Validated number
 */
function validateNumber(value, min = 0, max = Infinity) {
    const num = parseFloat(value);
    
    if (isNaN(num)) {
        throw new Error('Invalid number');
    }
    
    if (num < min || num > max) {
        throw new Error(`Number must be between ${min} and ${max}`);
    }
    
    return num;
}

/**
 * Sanitize object for API transmission
 * @param {Object} data - Data object to sanitize
 * @returns {Object} - Sanitized object
 */
function sanitizeApiData(data) {
    const sanitized = {};
    
    for (const [key, value] of Object.entries(data)) {
        if (typeof value === 'string') {
            // Remove null bytes and trim
            sanitized[key] = value.replace(/\x00/g, '').trim();
        } else if (typeof value === 'number') {
            sanitized[key] = value;
        } else if (typeof value === 'boolean') {
            sanitized[key] = value;
        } else if (Array.isArray(value)) {
            sanitized[key] = value;
        } else {
            sanitized[key] = value;
        }
    }
    
    return sanitized;
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        sanitizeUrl,
        createTextNode,
        createElement,
        validateNumber,
        sanitizeApiData
    };
}
