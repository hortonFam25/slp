import { Configuration, PopupRequest } from "@azure/msal-browser";

// MSAL configuration
export const msalConfig: Configuration = {
    auth: {
        clientId: import.meta.env.VITE_AAD_CLIENT_ID || 'REPLACE_ME',
        authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AAD_TENANT_ID || 'common'}`,
        redirectUri: import.meta.env.VITE_AAD_REDIRECT_URI || window.location.origin,
    },
    cache: {
        cacheLocation: "localStorage",
        storeAuthStateInCookie: false,
    }
};

// API scopes - for your custom API
export const appScopes = [
    "api://604604d7-697a-4111-8845-a1bc1014bd49/access_as_user",
    "offline_access",
    "openid", 
    "profile"
];

// Login request for acquiring tokens
export const loginRequest: PopupRequest = {
    scopes: appScopes
};

// Silent token request
export const tokenRequest = {
    scopes: appScopes,
    forceRefresh: false
};
