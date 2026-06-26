"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const supabase = createClient();
      const { error: authError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { display_name: name },
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (authError) throw authError;
      router.push("/cv");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Oprettelse mislykkedes. Prøv igen."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Opret konto</h1>
        <p className="mt-1 text-sm text-slate-500">
          Begynd at bygge din karriere med AI
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <Input
        id="name"
        type="text"
        label="Navn"
        placeholder="Dit fulde navn"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        autoComplete="name"
      />

      <Input
        id="email"
        type="email"
        label="E-mail"
        placeholder="din@email.dk"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
      />

      <Input
        id="password"
        type="password"
        label="Adgangskode"
        placeholder="Min. 8 tegn"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
        autoComplete="new-password"
      />

      <Button type="submit" className="w-full" size="lg" loading={loading}>
        Opret konto
      </Button>

      <p className="text-center text-xs text-slate-400 leading-relaxed">
        Ved at oprette en konto accepterer du vores{" "}
        <Link href="/terms" className="underline hover:text-slate-600">Brugsbetingelser</Link>
        {" "}og{" "}
        <Link href="/privacy" className="underline hover:text-slate-600">Privatlivspolitik</Link>.
      </p>

      <p className="text-center text-sm text-slate-500">
        Har du allerede en konto?{" "}
        <Link
          href="/login"
          className="font-medium text-blue-600 hover:text-blue-700"
        >
          Log ind
        </Link>
      </p>
    </form>
  );
}
