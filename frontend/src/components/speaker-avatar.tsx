import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { apiUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  speaker: string;
  initials: string;
  photoUrl: string | null;
  named: boolean;
  size?: "sm" | "default" | "lg";
  className?: string;
};

/**
 * Official portrait (thumbnail of the parlimen.gov.my photo) when the seat AND name matched
 * (speakers/photos.py); otherwise initials from the registry, or "?" for an unnamed member.
 * No status dot: "online/busy" means nothing for a transcript, and a coloured dot beside an MP reads as a judgement.
 */
export function SpeakerAvatar({ speaker, initials, photoUrl, named, size = "default", className }: Props) {
  return (
    <Avatar size={size} className={className} aria-label={speaker}>
      {photoUrl && named ? <AvatarImage src={apiUrl(photoUrl)} alt="" className="object-[50%_15%]" /> : null}
      <AvatarFallback className={cn("font-medium", size === "sm" && "text-[10px]")}>{named ? initials : "?"}</AvatarFallback>
    </Avatar>
  );
}
