import { Suspense } from "react";
import { Chat } from "@/components/Chat";

export const metadata = { title: "Pitwall · Ask the pit wall" };

export default function ChatPage() {
  return (
    <Suspense>
      <Chat />
    </Suspense>
  );
}
