import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';
import { MsalProvider } from '@azure/msal-react';
import { PublicClientApplication, EventType, AccountInfo } from '@azure/msal-browser';
import App from './App';
import './index.css';

const msalInstance = new PublicClientApplication({
  auth: {
    clientId: import.meta.env.VITE_AAD_CLIENT_ID || 'REPLACE_ME',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AAD_TENANT_ID || 'common'}`,
    redirectUri: import.meta.env.VITE_AAD_REDIRECT_URI || window.location.origin,
  },
  cache: {
    cacheLocation: 'localStorage',
    storeAuthStateInCookie: false,
  }
});

// Handle redirects immediately when app loads
msalInstance.handleRedirectPromise().then((response) => {
  if (response && response.account) {
    msalInstance.setActiveAccount(response.account);
  } else {
    // Set active account from cache if available
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }
});

msalInstance.addEventCallback((event) => {
  if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
    const account = (event.payload as { account: AccountInfo }).account;
    msalInstance.setActiveAccount(account);
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster position="top-right" />
        </BrowserRouter>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </MsalProvider>
  </React.StrictMode>
);


