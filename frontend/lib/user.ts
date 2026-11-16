"use client";

import { useEffect, useState } from "react";

export const USER_STORAGE_KEY = "kaogong.user_id";
export const DEFAULT_USER_ID = "local-user";
const USER_EVENT = "kaogong-user-change";

export function normalizeUserId(value: string): string {
  const cleaned = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return cleaned || DEFAULT_USER_ID;
}

export function getUserId(): string {
  if (typeof window === "undefined") return DEFAULT_USER_ID;
  try {
    return normalizeUserId(
      window.localStorage.getItem(USER_STORAGE_KEY) ?? DEFAULT_USER_ID,
    );
  } catch {
    return DEFAULT_USER_ID;
  }
}

export function setUserId(value: string): string {
  const id = normalizeUserId(value);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(USER_STORAGE_KEY, id);
    window.dispatchEvent(new Event(USER_EVENT));
  }
  return id;
}

export function useUserId(): string {
  const [userId, setId] = useState(DEFAULT_USER_ID);

  useEffect(() => {
    setId(getUserId());
    const sync = () => setId(getUserId());
    window.addEventListener(USER_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(USER_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return userId;
}
