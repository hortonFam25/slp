import React, { useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useMsal, useIsAuthenticated } from '@azure/msal-react';
import { InteractionStatus } from '@azure/msal-browser';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import { AlertTriangle, Brain, ShieldCheck, Sparkles } from 'lucide-react';

import { appScopes } from '../../lib/auth/authConfig';
import { capturePendingConsent, clearPendingConsent } from '../../lib/auth/pendingConsent';
import { oauthApi } from '../../lib/api/oauth';
import type { OAuthConsentInput } from '../../lib/api/oauth';

/**
 * The parameters the backend forwarded from /oauth/authorize, in OAuth's own
 * snake_case. `clientName` is the one extra: the server knows it from the
 * dynamic registration and passes it along so this screen can NAME who is
 * asking.
 */
export type ConsentParams = {
  clientId: string;
  clientName: string | null;
  redirectUri: string;
  state: string | null;
  codeChallenge: string;
  codeChallengeMethod: string;
  resource: string | null;
};

/**
 * Plain fields rather than a discriminated union: this project compiles with
 * `strict: false`, where narrowing a `{ok: true} | {ok: false}` union does not
 * survive, and a shape that needs no narrowing cannot break the build.
 * Exactly one of the two is ever set.
 */
export type ConsentParamCheck = {
  params: ConsentParams | null;
  reason: string | null;
};

/**
 * Validate the query string BEFORE anything is shown or sent.
 *
 * Deliberately mirrors the server's own checks rather than trusting them: this
 * page is reachable by typing the URL, and the failure mode of a half-formed
 * request must be a dead-end card, never a redirect. Bouncing to an
 * unvalidated `redirect_uri` is exactly the open redirect the OAuth rules
 * exist to prevent, so nothing here ever navigates on error.
 */
export function readConsentParams(search: URLSearchParams): ConsentParamCheck {
  const clientId = (search.get('client_id') ?? '').trim();
  const redirectUri = (search.get('redirect_uri') ?? '').trim();
  const codeChallenge = (search.get('code_challenge') ?? '').trim();
  // Absent means the RFC default, "plain" - which we reject, same as the server.
  const method = (search.get('code_challenge_method') ?? '').trim();
  const responseType = (search.get('response_type') ?? 'code').trim();

  const refuse = (reason: string): ConsentParamCheck => ({ params: null, reason });

  if (!clientId) return refuse("It didn't say which app is asking.");
  if (!redirectUri) return refuse("It didn't say where to send you back to.");
  if (responseType !== 'code') {
    return refuse("It asked for a kind of connection we don't hand out.");
  }
  if (!codeChallenge || method.toUpperCase() !== 'S256') {
    return refuse("It didn't include the security check we require.");
  }

  const clientName = (search.get('client_name') ?? '').trim();
  return {
    reason: null,
    params: {
      clientId,
      clientName: clientName || null,
      redirectUri,
      state: search.get('state'),
      codeChallenge,
      codeChallengeMethod: 'S256',
      resource: search.get('resource'),
    },
  };
}

/** One frame for every state this page can be in. */
function Screen({ children }: { children: React.ReactNode }) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 2,
      }}
    >
      <Card sx={{ width: '100%', maxWidth: 520, borderRadius: 3, boxShadow: 6 }}>
        <CardContent sx={{ p: 4 }}>
          <Stack direction="row" alignItems="center" gap={1.5} mb={3}>
            <Box
              sx={{
                p: 1,
                bgcolor: 'rgba(65, 170, 183, 0.15)',
                borderRadius: 2,
                display: 'flex',
                color: '#41AAB7',
              }}
            >
              <Brain size={24} />
            </Box>
            <Box>
              <Typography variant="h6" fontWeight={800} lineHeight={1.1}>
                SLP Pro
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Connection request
              </Typography>
            </Box>
          </Stack>
          {children}
        </CardContent>
      </Card>
    </Box>
  );
}

/** A dead end: a malformed link and a refused request both land here. */
function Problem({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Screen>
      <Stack direction="row" gap={1} alignItems="center" color="error.main" mb={1}>
        <AlertTriangle size={18} />
        <Typography variant="subtitle1" fontWeight={700}>
          {title}
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary">
        {children}
      </Typography>
      <Typography variant="caption" color="text.disabled" display="block" mt={2}>
        Nothing was connected and nobody was sent anywhere. Go back to Claude and add the
        connector again - that builds a fresh link.
      </Typography>
    </Screen>
  );
}

/**
 * /connect/authorize - the one screen a therapist sees when Claude asks for
 * access to his caseload.
 *
 * It sits outside the AppShell on purpose: this is not a page of the app, it
 * is a decision about the app, and the nav chrome around it would invite
 * wandering off mid-flow. Sign-in still applies - a signed-out therapist is
 * asked to sign in right here, and the request is stashed first so it survives
 * the round trip through Entra (see lib/auth/pendingConsent).
 */
export default function ConnectAuthorize() {
  const [search] = useSearchParams();
  const { params, reason } = useMemo(() => readConsentParams(search), [search]);
  const isAuthenticated = useIsAuthenticated();
  const { instance, inProgress } = useMsal();

  // Keep the request alive across the sign-in redirect. Runs on every render
  // path, including the signed-in one, because MSAL can decide mid-session
  // that it needs interaction again.
  useEffect(() => {
    capturePendingConsent();
  }, []);

  // The hand-off OUT of the SPA: the server owns this URL (it is the client's
  // registered callback), so the router must not try to route it.
  const go = (result: { redirectUrl: string }) => {
    clearPendingConsent();
    window.location.assign(result.redirectUrl);
  };

  const approve = useMutation({
    mutationFn: (payload: OAuthConsentInput) => oauthApi.consent(payload),
    onSuccess: go,
  });
  const deny = useMutation({
    mutationFn: (payload: OAuthConsentInput) => oauthApi.deny(payload),
    onSuccess: go,
  });
  const busy = approve.isPending || deny.isPending;

  if (!params) {
    return <Problem title="That connection link isn't complete">{reason}</Problem>;
  }

  /*
   * The name is the anti-phishing detail, so it is used the moment it exists.
   * It only exists if /oauth/authorize forwarded `client_name` from the
   * registration - the OAuth request itself never carries one - so the
   * fallback has to read like a finished sentence rather than a gap.
   */
  const asking = params.clientName ?? 'The app you are connecting';

  if (!isAuthenticated) {
    return (
      <Screen>
        <Typography variant="subtitle1" fontWeight={700} gutterBottom>
          Sign in to continue
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {asking} is asking to connect to your SLP Pro caseload. Sign in with your work
          account first - SLP Pro never sees your password, and nothing is connected until
          you approve it on the next screen.
        </Typography>
        <Button
          variant="contained"
          fullWidth
          size="large"
          sx={{ mt: 3, textTransform: 'none', fontWeight: 600 }}
          disabled={inProgress !== InteractionStatus.None}
          onClick={() => {
            capturePendingConsent();
            void instance.loginRedirect({ scopes: appScopes });
          }}
        >
          {inProgress !== InteractionStatus.None ? 'Signing in...' : 'Sign in with Microsoft'}
        </Button>
      </Screen>
    );
  }

  const body = (): OAuthConsentInput => ({
    clientId: params.clientId,
    redirectUri: params.redirectUri,
    state: params.state,
    codeChallenge: params.codeChallenge,
    codeChallengeMethod: params.codeChallengeMethod,
    resource: params.resource,
  });

  const error = approve.error ?? deny.error;

  return (
    <Screen>
      <Stack direction="row" gap={1} alignItems="center" mb={1}>
        <Sparkles size={18} color="#41AAB7" />
        <Typography variant="subtitle1" fontWeight={800}>
          Connect Claude to SLP Pro
        </Typography>
      </Stack>

      <Typography variant="body2" color="text.secondary">
        <strong>{asking}</strong> is asking to work with your caseload the way you do: read
        your students, their eligibilities, IEP goals and objectives, progress data, therapy
        sessions and schedule - and record the same kinds of updates you can record yourself.
      </Typography>

      <Divider sx={{ my: 2.5 }} />

      <Stack spacing={1.25}>
        {[
          'Your caseload only. It sees exactly the students you can see, checked fresh on every request.',
          'Never more than you can do yourself. Your password is never shared with Claude.',
          'You can disconnect it at any time from Settings, and the connection ends immediately.',
        ].map((line) => (
          <Stack key={line} direction="row" gap={1.25} alignItems="flex-start">
            <Box sx={{ color: 'success.main', mt: '2px', display: 'flex' }}>
              <ShieldCheck size={16} />
            </Box>
            <Typography variant="body2" color="text.secondary">
              {line}
            </Typography>
          </Stack>
        ))}
      </Stack>

      {error ? (
        <Alert severity="error" sx={{ mt: 2.5 }}>
          {(error as { message?: string })?.message ??
            "We couldn't finish connecting. Try the link again."}
        </Alert>
      ) : null}

      <Button
        variant="contained"
        fullWidth
        size="large"
        sx={{ mt: 3, textTransform: 'none', fontWeight: 700 }}
        disabled={busy}
        onClick={() => approve.mutate(body())}
        startIcon={approve.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}
      >
        {approve.isPending ? 'Connecting...' : 'Approve'}
      </Button>

      <Button
        variant="text"
        fullWidth
        sx={{ mt: 1, textTransform: 'none' }}
        disabled={busy}
        onClick={() => deny.mutate(body())}
      >
        {deny.isPending ? 'Cancelling...' : 'Cancel'}
      </Button>

      <Typography variant="caption" color="text.disabled" display="block" align="center" mt={2}>
        Didn't start this in Claude? Press Cancel - nothing is connected until you approve.
      </Typography>
    </Screen>
  );
}
