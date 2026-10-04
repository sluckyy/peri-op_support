-- Real username/password authentication for staff/clinician access --
-- see periop_core.auth's module docstring for scope and periop_api.app
-- for which endpoints require it. Patients submitting their own data
-- (creating a session, acknowledging the notice, adding an assertion)
-- stay unauthenticated; anyone viewing session data or taking a
-- clinical/Model-Layer action must hold a valid session token.

CREATE TABLE app_user (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth_session (
    token      TEXT PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES app_user (user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_auth_session_user_id ON auth_session (user_id);
