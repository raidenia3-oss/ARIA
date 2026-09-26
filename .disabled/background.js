chrome.runtime.onInstalled.addListener(() => {
  console.log('AURA Fanfic Generator installed');
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'sync' && changes.auraBackendUrl) {
    console.log('AURA backend URL updated:', changes.auraBackendUrl.newValue);
  }
});
