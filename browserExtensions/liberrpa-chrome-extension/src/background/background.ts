// FileName: background.ts
import { setupSocket } from "./socketFun";

console.info("This is background.js");

// Setup socket when the service worker starts.
// This also covers extension reload.
void setupSocket();

// Inject content scripts into all existing tabs after installation or update
chrome.runtime.onInstalled.addListener(() => {
  console.log("Extension installed or updated. Inject content script.");
  injectContentScripts();
});

// Run when Chrome starts
chrome.runtime.onStartup.addListener(() => {
  console.log("Chrome started. Inject content script.");
  injectContentScripts();
});

// Function to inject content scripts into all open tabs
function injectContentScripts() {
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach((tab) => {
      if (tab.id && tab.url && !tab.url.startsWith("chrome://")) {
        chrome.scripting
          .executeScript({
            target: { tabId: tab.id },
            files: ["dist/content.js"],
          })
          .then((_) => {
            console.info("Injected content script into " + tab.url);
          })
          .catch((err) => console.error(`Error injecting script into tab ${tab.id}:`, err));
      }
    });
  });
}

