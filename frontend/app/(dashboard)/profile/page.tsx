import { UserRound } from "lucide-react";

export default function ProfilePage() {
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-3xl font-semibold">Profile</h1>
        <p className="mt-2 text-zinc-600">Manage account details used by future sizing recommendations.</p>
      </div>
      <section className="rounded-lg border border-zinc-200 bg-white p-5">
        <div className="flex items-center gap-3">
          <UserRound className="h-5 w-5 text-lilac" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Personal details</h2>
        </div>
        <form className="mt-5 grid gap-4 md:grid-cols-2">
          <input className="h-11 rounded-md border border-zinc-300 px-3" placeholder="First name" />
          <input className="h-11 rounded-md border border-zinc-300 px-3" placeholder="Last name" />
          <input className="h-11 rounded-md border border-zinc-300 px-3" placeholder="Country code" />
          <button className="h-11 rounded-md bg-ink px-4 text-sm font-semibold text-white md:w-fit" type="button">
            Save profile
          </button>
        </form>
      </section>
    </div>
  );
}

