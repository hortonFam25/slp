import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'react-hot-toast';
import { MsalProvider } from '@azure/msal-react';
import { PublicClientApplication, EventType, AccountInfo } from '@azure/msal-browser';
import App from './App';
import { dbWakeAwareRetry, dbWakeAwareRetryDelay } from './lib/db-wake/queryRetry';
import { capturePendingConsent } from './lib/auth/pendingConsent';
import './index.css';

// BEFORE MSAL touches the URL: if this load is a connector consent request,
// remember its query string. Entra returns to the bare origin and the OAuth
// parameters cannot be reconstructed, so a request that is not stashed here is
// a connector that fails with nothing to explain it.
capturePendingConsent();

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

(window as unknown as { __msalInstance?: PublicClientApplication }).__msalInstance = msalInstance;

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
      // Was `retry: 1`. The axios db-wake interceptor now owns retries for a
      // paused database — it absorbs those failures entirely, so a query only
      // ever sees an error the interceptor already gave up on or deliberately
      // declined. Retrying those here would stack a second storm on top of a
      // two-minute wait. lib/db-wake/queryRetry.ts documents the interplay.
      retry: dbWakeAwareRetry,
      retryDelay: dbWakeAwareRetryDelay,
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


