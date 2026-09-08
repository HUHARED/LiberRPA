# Privacy Policy for LiberRPA Chrome Extension

Last updated: September 8, 2026

LiberRPA Chrome Extension is the browser integration component of LiberRPA. It connects supported Google Chrome pages to LiberRPA Local Server running on the same computer so that user-requested browser automation can be performed.

## Data the Extension May Process

Depending on the automation operation requested by the user, the Extension may process browser data including:

- web page content and DOM information;
- form values and element attributes;
- page URLs and tab or window information;
- navigation information;
- cookies when a LiberRPA automation explicitly performs cookie operations;
- download information when a LiberRPA automation explicitly performs download operations;
- operation results and error information required to complete the requested automation.

The Extension does not independently browse websites or collect browser data for analytics, advertising, profiling, or other unrelated purposes.

Data is accessed only as needed to perform LiberRPA browser automation requested by the user.

## How Data Is Used

Browser data is used only to provide LiberRPA browser automation features, including:

- locating and interacting with HTML elements;
- reading information requested by an automation;
- navigating supported web pages;
- managing tabs and windows;
- performing requested cookie and download operations;
- returning automation results to LiberRPA.

The Extension does not use browser data for advertising, user profiling, creditworthiness, or marketing.

## Local Communication

The Extension communicates with LiberRPA Local Server running on the same computer.

LiberRPA Local Server listens on the local loopback interface and uses local authentication information generated during LiberRPA initialization.

Browser automation data is exchanged locally between the Extension, LiberRPA Local Server, and the user's LiberRPA automation.

The Extension does not send browsing data or page content to a LiberRPA-operated cloud service.

## Data Storage and Retention

The Extension does not operate a remote data store for browser data.

Browser data processed by the Extension is normally used transiently to perform the requested automation and return its result locally.

A user's LiberRPA Project may intentionally save automation results, screenshots, downloads, logs, or other output to local storage when the Project is designed to do so. Such storage is controlled by the user's automation and local LiberRPA configuration.

## Data Sharing

LiberRPA does not sell browser data or user data.

The Extension does not share browser data with advertisers, data brokers, or other third parties for advertising, profiling, or resale.

Data required for browser automation is passed only to local LiberRPA components and the user's automation on the same computer, except where the user's own automation explicitly communicates with an external service.

## User Control

Users control when LiberRPA browser automation runs.

Users can stop browser automation by stopping the relevant LiberRPA Project, stopping LiberRPA Local Server, disabling the Chrome Extension, or uninstalling the Extension.

Locally generated automation outputs can be managed or deleted by the user from their own computer.

## Security

LiberRPA Chrome Extension uses local authentication when communicating with LiberRPA Local Server.

Authentication information is generated locally during LiberRPA initialization and is not intended to be publicly disclosed.

## Chrome Web Store Limited Use

The use of information received from Google APIs will adhere to the Chrome Web Store User Data Policy, including the Limited Use requirements.

## Open Source

LiberRPA Chrome Extension is open-source software.

Source code:
https://github.com/HUHARED/LiberRPA/tree/main/browserExtensions/liberrpa-chrome-extension

## Contact

Questions about this privacy policy can be submitted through the LiberRPA community and support channels:

https://github.com/HUHARED/LiberRPA#community--support
