"use client";

import { CalendarRange, Landmark, Plus, User, Users, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { apiUrl, type Filters, type PartyOption, type Speaker, type Status } from "@/lib/api";
import { coverage, dateMs } from "@/lib/copy";
import { cn } from "@/lib/utils";

const FIRST_SITTING = "2022-12-19"; // 15th Parliament's first sitting; only a fallback until /api/status says what is indexed

const chip =
  "inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-[13px] transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50";
const idle = "text-muted-foreground shadow-[inset_0_0_0_1px_var(--border-default)] hover:text-foreground hover:shadow-[inset_0_0_0_1px_var(--border-strong)]";
const active = "bg-primary text-primary-foreground";

function ActiveChip({ icon, label, onClear }: { icon: ReactNode; label: string; onClear: () => void }) {
  return (
    <span className={cn(chip, active, "pe-1")}>
      {icon}
      <span className="max-w-[16rem] truncate">{label}</span>
      <button
        type="button"
        onClick={onClear}
        aria-label={`Buang penapis ${label}`}
        className="grid size-6 place-items-center rounded-full hover:bg-primary-foreground/15"
      >
        <X className="size-3.5" />
      </button>
    </span>
  );
}

/** Filters as chips under the search bar (spec: chips, not a settings page). */
export function FilterChips({ value, onChange, status }: { value: Filters; onChange: (f: Filters) => void; status: Status | null }) {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [speakerOpen, setSpeakerOpen] = useState(false);
  const [parties, setParties] = useState<PartyOption[]>([]);
  const [partyOpen, setPartyOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [from, setFrom] = useState(value.dateFrom ?? "");
  const [to, setTo] = useState(value.dateTo ?? "");

  useEffect(() => {
    fetch(apiUrl("/api/speakers"))
      .then((r) => r.json())
      .then(setSpeakers)
      .catch(() => setSpeakers([]));
    fetch(apiUrl("/api/parties"))
      .then((r) => r.json())
      .then(setParties)
      .catch(() => setParties([]));
  }, []);

  const minDate = status?.from ?? FIRST_SITTING;
  const maxDate = status?.to ?? undefined;
  const speaker = speakers.find((s) => s.id === value.speakerId);
  const dateLabel =
    value.dateFrom && value.dateTo
      ? `${dateMs(value.dateFrom)} – ${dateMs(value.dateTo)}`
      : value.dateFrom
        ? `Dari ${dateMs(value.dateFrom)}`
        : value.dateTo
          ? `Hingga ${dateMs(value.dateTo)}`
          : null;

  return (
    <div className="-mx-4 -my-1 flex items-center gap-2 overflow-x-auto px-4 py-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden">
      <Tooltip>
        <TooltipTrigger render={<span className={cn(chip, "px-1 text-muted-foreground")} />}>
          <Landmark className="size-3.5" /> Parlimen ke-15
        </TooltipTrigger>
        <TooltipContent>{status ? `Diindeks buat masa ini: ${coverage(status)}` : "Satu-satunya penggal yang diindeks buat masa ini"}</TooltipContent>
      </Tooltip>

      {value.speakerId ? (
        <ActiveChip
          icon={<User className="size-3.5" />}
          label={speaker?.label ?? value.speakerId}
          onClear={() => onChange({ ...value, speakerId: null })}
        />
      ) : (
        <Popover open={speakerOpen} onOpenChange={setSpeakerOpen}>
          <PopoverTrigger className={cn(chip, idle)}>
            <Plus className="size-3.5" /> Ahli Parlimen
          </PopoverTrigger>
          <PopoverContent align="start" className="w-80 p-0">
            <Command>
              <CommandInput placeholder="Nama atau kawasan…" />
              <CommandList className="max-h-72">
                <CommandEmpty>Tiada padanan dalam daftar.</CommandEmpty>
                {speakers.map((s) => (
                  <CommandItem
                    key={s.id}
                    value={s.label}
                    onSelect={() => {
                      onChange({ ...value, speakerId: s.id });
                      setSpeakerOpen(false);
                    }}
                  >
                    {s.label}
                  </CommandItem>
                ))}
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}

      {value.party ? (
        <ActiveChip
          icon={<Users className="size-3.5" />}
          label={`Parti semasa: ${value.party}`}
          onClear={() => onChange({ ...value, party: null })}
        />
      ) : (
        <Popover open={partyOpen} onOpenChange={setPartyOpen}>
          <PopoverTrigger className={cn(chip, idle)} disabled={parties.length === 0}>
            <Plus className="size-3.5" /> Parti
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-0">
            <Command>
              <CommandInput placeholder="Cari parti…" />
              <CommandList className="max-h-72">
                <CommandEmpty>Tiada parti.</CommandEmpty>
                {parties.map((p) => (
                  <CommandItem
                    key={p.party}
                    value={p.party}
                    onSelect={() => {
                      onChange({ ...value, party: p.party });
                      setPartyOpen(false);
                    }}
                  >
                    {p.party}
                    <span className="ms-auto text-xs text-muted-foreground">{p.members} ahli</span>
                  </CommandItem>
                ))}
              </CommandList>
            </Command>
            <p className="border-t px-3 py-2 text-xs text-muted-foreground">
              Parti semasa menurut profil rasmi Parlimen; belum mengikut tarikh sidang.
            </p>
          </PopoverContent>
        </Popover>
      )}

      {dateLabel ? (
        <ActiveChip
          icon={<CalendarRange className="size-3.5" />}
          label={dateLabel}
          onClear={() => onChange({ ...value, dateFrom: null, dateTo: null })}
        />
      ) : (
        <Popover
          open={dateOpen}
          onOpenChange={(open) => {
            if (open) {
              setFrom(value.dateFrom ?? "");
              setTo(value.dateTo ?? "");
            }
            setDateOpen(open);
          }}
        >
          <PopoverTrigger className={cn(chip, idle)}>
            <Plus className="size-3.5" /> Tarikh
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72">
            <form
              className="grid gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                onChange({ ...value, dateFrom: from || null, dateTo: to || null });
                setDateOpen(false);
              }}
            >
              <label className="grid gap-1 text-xs text-muted-foreground">
                Dari
                <Input type="date" min={minDate} max={to || maxDate} value={from} onChange={(e) => setFrom(e.target.value)} />
              </label>
              <label className="grid gap-1 text-xs text-muted-foreground">
                Hingga
                <Input type="date" min={from || minDate} max={maxDate} value={to} onChange={(e) => setTo(e.target.value)} />
              </label>
              {status?.from && status?.to ? (
                <p className="text-xs text-subtle">
                  Hanya sidang {dateMs(status.from)} – {dateMs(status.to)} diindeks.
                </p>
              ) : null}
              <Button type="submit" disabled={!from && !to}>
                Guna tarikh
              </Button>
            </form>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
