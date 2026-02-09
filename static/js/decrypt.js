function decryptText(element) {
    // This is a placeholder function. In a real implementation, you would replace this with actual decryption logic.
    // For demonstration, we'll just reverse the text back to normal.
    const decoded = atob(element.dataset.enc);
    element.innerText = decoded;
    element.onclick = null; // Remove click handler after decryption
}