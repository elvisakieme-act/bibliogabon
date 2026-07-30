import { apiRequest } from "@/api/client";
import type { ApiUser, AuthTokens } from "@/api/types";

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
}

export interface ProfileUpdateInput {
  display_name?: string;
}

export function registerIndividual(input: RegisterInput) {
  return apiRequest<{ user: ApiUser; tokens: AuthTokens }>("/api/v1/auth/register/", {
    method: "POST",
    body: input
  });
}

export function login(email: string, password: string) {
  return apiRequest<AuthTokens>("/api/v1/auth/token/", {
    method: "POST",
    body: { email, password }
  });
}

export function refreshToken(refresh: string) {
  return apiRequest<AuthTokens>("/api/v1/auth/token/refresh/", {
    method: "POST",
    body: { refresh }
  });
}

export function logout(refresh: string, access: string) {
  return apiRequest<void>("/api/v1/auth/logout/", {
    method: "POST",
    token: access,
    body: { refresh }
  });
}

export function getCurrentUser(access: string) {
  return apiRequest<ApiUser>("/api/v1/me/", { token: access });
}

export function updateCurrentUser(access: string, input: ProfileUpdateInput) {
  return apiRequest<ApiUser>("/api/v1/me/", {
    method: "PATCH",
    token: access,
    body: input
  });
}
