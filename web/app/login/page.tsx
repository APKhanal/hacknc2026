import { Suspense } from "react";
import type { Metadata } from "next";
import { LoginScreen } from "@/components/auth/login-screen";

export const metadata: Metadata = { title: "Pocketwatch — Sign in" };

export default function LoginPage() {
  // useSearchParams (for ?next=) needs a Suspense boundary.
  return <Suspense><LoginScreen /></Suspense>;
}
