"use client";

import { useMemo, useState } from "react";

type TagSelectorProps = {
  tags: Array<{ tag_id: string; tag_name: string }>;
  selectedTagIds: string[];
  onToggle: (tagId: string) => void;
};

export function TagSelector({ tags, selectedTagIds, onToggle }: Readonly<TagSelectorProps>) {
  const selectedCount = selectedTagIds.length;
  const [query, setQuery] = useState("");
  const filteredTags = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? tags.filter((t) => t.tag_name.toLowerCase().includes(q)) : tags;
  }, [query, tags]);

  return (
    <div className="space-y-4">
      <div>
        <label className="ui-label block">Search tags</label>
        <input
          className="ui-input"
          placeholder="React, backend, SQL, automation"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="ui-panel flex items-center justify-between">
        <p className="ui-kicker">{filteredTags.length} available</p>
        <p className="ui-kicker">{selectedCount} selected</p>
      </div>

      {filteredTags.length === 0 ? (
        <p className="ui-empty text-center">No matching tags.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filteredTags.map((tag, index) => {
            const selected = selectedTagIds.includes(tag.tag_id);
            return (
              <button
                key={tag.tag_id}
                type="button"
                data-selected={selected}
                onClick={() => onToggle(tag.tag_id)}
                className="ui-chip ui-stagger flex min-h-16 items-center justify-between px-4 py-3 text-left"
                style={{ ["--index" as string]: index }}
              >
                <span className="truncate text-sm font-medium">{tag.tag_name}</span>
                <span className={`ui-status ${selected ? "ui-status-green" : "bg-[var(--green-mist)] text-[var(--text-soft)]"}`}>
                  {selected ? "Selected" : "Add"}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
