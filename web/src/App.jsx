import { useEffect, useMemo, useRef, useState } from "react";
import { stations as defaultStations } from "./stations.js";

const CUSTOM_STREAMS_KEY = "radioPlayer.customStreams";
const LOGO_OVERRIDES_KEY = "radioPlayer.logoOverrides";
const STATION_OVERRIDES_KEY = "radioPlayer.stationOverrides";
const DELETED_STATIONS_KEY = "radioPlayer.deletedStations";
const VIEW_MODE_KEY = "radioPlayer.viewMode";
const HIDDEN_STATIONS_KEY = "radioPlayer.hiddenStations";
const THEME_MODE_KEY = "radioPlayer.themeMode";
const FX_ENABLED_KEY = "radioPlayer.fxEnabled";
const FX_MODE_KEY = "radioPlayer.fxMode";
const VOLUME_KEY = "radioPlayer.volume";
const MUTED_KEY = "radioPlayer.muted";
const LAST_STATION_KEY = "radioPlayer.lastStation";
const AUDIO_EXTENSIONS = new Set([".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".webm"]);
const FX_MODES = ["Warp Speed", "Kinetic Sparks", "Digital Rain"];
const THEME_PRESETS = {
  Auto: "auto",
  "Cyan Neon": "#45f3ff",
  "Emerald Matrix": "#00ff66",
  "Amber Retro": "#ffb300",
  "Hot Pink": "#ff007f",
  "Sunset Orange": "#ff5500",
  "Purple Velvet": "#b300ff",
  "Midnight Blue": "#0055ff",
  "Slime Green": "#aae600",
};

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function isAudioFile(name) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 && AUDIO_EXTENSIONS.has(name.slice(dotIndex).toLowerCase());
}

function readJson(key, fallback) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function readBoolean(key, fallback) {
  const value = localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }
  return value === "true";
}

function readNumber(key, fallback) {
  const value = Number(localStorage.getItem(key));
  return Number.isFinite(value) ? value : fallback;
}

function stationKey(station) {
  return station.id || station.name || station.url;
}

function hasStoredKey(keys, station) {
  return keys.includes(stationKey(station)) || (station.url ? keys.includes(station.url) : false);
}

function formatStreamMetadata(station, metadata) {
  const title = metadata?.title?.trim();
  const artist = metadata?.artist?.trim();
  const album = metadata?.album?.trim();
  const parts = [artist, title].filter(Boolean);

  if (parts.length) {
    const combined = parts.join(" - ");
    return combined.toLowerCase() === station.name.toLowerCase() ? "" : combined;
  }

  if (title) {
    return title.toLowerCase() === station.name.toLowerCase() ? "" : title;
  }

  if (album && album.toLowerCase() !== station.name.toLowerCase()) {
    return album;
  }

  return "";
}

function getStartupStation() {
  const hiddenStations = readJson(HIDDEN_STATIONS_KEY, []);
  const customStreams = readJson(CUSTOM_STREAMS_KEY, []);
  const stationOverrides = readJson(STATION_OVERRIDES_KEY, {});
  const deletedStations = readJson(DELETED_STATIONS_KEY, []);
  const lastStationKey = localStorage.getItem(LAST_STATION_KEY);
  const restoredDefaults = defaultStations
    .filter((station) => !hasStoredKey(deletedStations, station))
    .map((station) => ({
      ...station,
      ...(stationOverrides[stationKey(station)] || stationOverrides[station.url] || {}),
    }));
  const visibleStations = [...restoredDefaults, ...customStreams].filter((station) => !hasStoredKey(hiddenStations, station));

  return visibleStations.find((station) => stationKey(station) === lastStationKey || station.url === lastStationKey) || visibleStations[0] || null;
}

function colorFromText(text) {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = text.charCodeAt(index) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 92% 58%)`;
}

async function accentFromImage(src, fallbackText) {
  if (!src) {
    return colorFromText(fallbackText);
  }

  return new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d", { willReadFrequently: true });
        canvas.width = 24;
        canvas.height = 24;
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let red = 0;
        let green = 0;
        let blue = 0;
        let count = 0;

        for (let index = 0; index < data.length; index += 16) {
          const alpha = data[index + 3];
          if (alpha < 80) {
            continue;
          }
          red += data[index];
          green += data[index + 1];
          blue += data[index + 2];
          count += 1;
        }

        if (!count) {
          resolve(colorFromText(fallbackText));
          return;
        }

        resolve(`rgb(${Math.round(red / count)} ${Math.round(green / count)} ${Math.round(blue / count)})`);
      } catch {
        resolve(colorFromText(fallbackText));
      }
    };
    image.onerror = () => resolve(colorFromText(fallbackText));
    image.src = src;
  });
}

async function collectAudioFiles(directoryHandle) {
  const tracks = [];

  async function walk(handle) {
    for await (const entry of handle.values()) {
      if (entry.kind === "file" && isAudioFile(entry.name)) {
        const file = await entry.getFile();
        tracks.push({
          name: file.name.replace(/\.[^.]+$/, ""),
          url: URL.createObjectURL(file),
        });
      }

      if (entry.kind === "directory") {
        await walk(entry);
      }
    }
  }

  await walk(directoryHandle);
  return tracks.sort((a, b) => a.name.localeCompare(b.name));
}

function StationArtwork({ station, large = false }) {
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    setImageFailed(false);
  }, [station.logo]);

  if (imageFailed || !station.logo) {
    return (
      <span className={large ? "logo-wrap large-logo-wrap" : "logo-wrap"} title="right click to change logo">
        <span className={large ? "fallback-logo large-fallback-logo" : "fallback-logo"}>{initials(station.name)}</span>
      </span>
    );
  }

  return (
    <span className={large ? "logo-wrap large-logo-wrap" : "logo-wrap"} title="right click to change logo">
      <img
        className={large ? "station-logo large-station-logo" : "station-logo"}
        src={station.logo}
        alt=""
        loading="lazy"
        onError={() => setImageFailed(true)}
      />
    </span>
  );
}

function StationTile({ station, active, onPlay, onRemove, onChangeLogo }) {
  return (
    <div className={`station-tile${active ? " active" : ""}`}>
      {onRemove ? (
        <button className="remove-station" type="button" aria-label={`Remove ${station.name}`} onClick={onRemove}>
          x
        </button>
      ) : null}
      <button
        className="station-play"
        type="button"
        aria-label={`Play ${station.name}`}
        onClick={() => onPlay(station)}
        onContextMenu={(event) => {
          event.preventDefault();
          onChangeLogo(station);
        }}
      >
        <StationArtwork station={station} />
        <span className="station-name">{station.name}</span>
      </button>
    </div>
  );
}

function CoverFlowView({ stations, selectedIndex, activeStation, onSelectRelative, onSelectIndex, onPlay, onRemove, onChangeLogo }) {
  const wheelLockRef = useRef(0);
  const touchStateRef = useRef({ x: 0, y: 0, moved: false, swiping: false });

  if (!stations.length) {
    return null;
  }

  const selectedStation = stations[selectedIndex] || stations[0];
  const visibleOffsets = stations.length === 1 ? [0] : [-2, -1, 0, 1, 2];

  function stationAtOffset(offset) {
    const index = (selectedIndex + offset + stations.length) % stations.length;
    return { index, station: stations[index] };
  }

  return (
    <section
      className="cover-stage"
      aria-label="Stations"
      tabIndex={0}
      onTouchStart={(event) => {
        const touch = event.touches[0];
        if (!touch) {
          return;
        }
        touchStateRef.current = {
          x: touch.clientX,
          y: touch.clientY,
          moved: false,
          swiping: false,
        };
      }}
      onTouchMove={(event) => {
        const touch = event.touches[0];
        if (!touch) {
          return;
        }

        const deltaX = touch.clientX - touchStateRef.current.x;
        const deltaY = touch.clientY - touchStateRef.current.y;

        if (!touchStateRef.current.swiping && Math.abs(deltaX) > 18 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
          touchStateRef.current.swiping = true;
          touchStateRef.current.moved = true;
        }

        if (touchStateRef.current.swiping) {
          event.preventDefault();
        }
      }}
      onTouchEnd={(event) => {
        const touch = event.changedTouches[0];
        if (!touch) {
          return;
        }

        const deltaX = touch.clientX - touchStateRef.current.x;
        const deltaY = touch.clientY - touchStateRef.current.y;

        if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
          onSelectRelative(deltaX < 0 ? 1 : -1);
        }

        touchStateRef.current = { x: 0, y: 0, moved: false, swiping: false };
      }}
      onWheel={(event) => {
        event.preventDefault();
        const now = Date.now();
        if (now - wheelLockRef.current < 140) {
          return;
        }
        wheelLockRef.current = now;
        onSelectRelative(event.deltaY > 0 ? 1 : -1);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          event.preventDefault();
          onSelectRelative(-1);
        }

        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          event.preventDefault();
          onSelectRelative(1);
        }

        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onPlay(selectedStation);
        }
      }}
    >
      <div className="cover-items">
        {visibleOffsets.map((offset) => {
          const { index, station } = stationAtOffset(offset);
          const isCenter = offset === 0;
          const active = activeStation && stationKey(activeStation) === stationKey(station);
          const offsetName = offset < 0 ? `m${Math.abs(offset)}` : `${offset}`;

          return (
            <button
              key={`${stationKey(station)}-${offset}`}
              className={`cover-item cover-offset-${offsetName}${isCenter ? " selected" : ""}${active ? " active" : ""}`}
              type="button"
              aria-label={isCenter ? `Play ${station.name}` : `Select ${station.name}`}
              onClick={() => {
                if (touchStateRef.current.moved) {
                  touchStateRef.current = { x: 0, y: 0, moved: false, swiping: false };
                  return;
                }

                if (isCenter) {
                  onPlay(station);
                } else {
                  onSelectIndex(index);
                }
              }}
              onContextMenu={(event) => {
                event.preventDefault();
                onChangeLogo(station);
              }}
            >
              {station.custom ? (
                <span
                  className="remove-station cover-remove"
                  role="button"
                  tabIndex={-1}
                  aria-label={`Remove ${station.name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onRemove(station);
                  }}
                >
                  x
                </span>
              ) : null}
              <StationArtwork station={station} large />
            </button>
          );
        })}
      </div>
    </section>
  );
}

function FxLayer({ enabled, mode }) {
  if (!enabled) {
    return null;
  }

  const countByMode = {
    "Warp Speed": 96,
    "Kinetic Sparks": 34,
    "Digital Rain": 40,
  };
  const count = countByMode[mode] || 40;

  function particleStyle(index) {
    const x = (index * 37 + 11) % 100;
    const y = (index * 53 + 17) % 100;
    const angle = mode === "Warp Speed" ? (index * (360 / count)) % 360 : (index * 17 + 9) % 360;
    const size = 4 + (index % 7) * 2;
    const length = 50 + (index % 11) * 9;
    const delay = index * -0.055;
    const tx = ((index * 41) % 180) - 90;
    const ty = ((index * 29) % 160) - 100;

    return {
      "--x": `${x}%`,
      "--y": `${y}%`,
      "--angle": `${angle}deg`,
      "--size": `${size}px`,
      "--length": `${length}px`,
      "--delay": `${delay}s`,
      "--tx": `${tx}px`,
      "--ty": `${ty}px`,
    };
  }

  return (
    <div className={`fx-layer fx-${mode.toLowerCase().replace(/\s+/g, "-")}`} aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <span key={index} style={particleStyle(index)} />
      ))}
    </div>
  );
}

function StationManager({ stations, hiddenStations, onToggleVisibility, onDelete, onEdit }) {
  return (
    <div className="station-manager">
      <div className="manager-title">Stations</div>
      <div className="manager-list">
        {stations.map((station) => {
          const key = stationKey(station);
          const hidden = hasStoredKey(hiddenStations, station);
          return (
            <div className="manager-row" key={key}>
              <span className={hidden ? "manager-name hidden" : "manager-name"}>{station.name}</span>
              <button type="button" onClick={() => onToggleVisibility(station)}>
                {hidden ? "Show" : "Hide"}
              </button>
              <button type="button" onClick={() => onEdit(station)}>
                Edit
              </button>
              <button type="button" className="danger-button" onClick={() => onDelete(station)}>
                Delete
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StationEditor({ station, url, message, onUrlChange, onChooseIcon, onSave, onCancel }) {
  if (!station) {
    return null;
  }

  const isFolder = station.type === "folder";

  return (
    <form className="station-editor" onSubmit={onSave}>
      <div className="options-heading">Edit Station</div>
      <div className="editor-title">{station.name}</div>
      <label>
        <span>Station URL</span>
        <input
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          placeholder="https://stream.example.com/live.mp3"
          aria-label="Station URL"
          disabled={isFolder}
        />
      </label>
      <div className="editor-actions">
        <button type="button" onClick={onChooseIcon}>
          Change Icon
        </button>
        <button type="submit" disabled={isFolder}>
          Save URL
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {message ? <span className="editor-message">{message}</span> : null}
    </form>
  );
}

export default function App() {
  const startupStation = getStartupStation();
  const audioRef = useRef(null);
  const fileInputRef = useRef(null);
  const logoInputRef = useRef(null);
  const logoTargetRef = useRef(null);
  const currentTrackUrls = useRef([]);
  const [customStreams, setCustomStreams] = useState(() => readJson(CUSTOM_STREAMS_KEY, []));
  const [folderStations, setFolderStations] = useState([]);
  const [logoOverrides, setLogoOverrides] = useState(() => readJson(LOGO_OVERRIDES_KEY, {}));
  const [stationOverrides, setStationOverrides] = useState(() => readJson(STATION_OVERRIDES_KEY, {}));
  const [deletedStations, setDeletedStations] = useState(() => readJson(DELETED_STATIONS_KEY, []));
  const [viewMode, setViewMode] = useState(() => localStorage.getItem(VIEW_MODE_KEY) || "tile");
  const [hiddenStations, setHiddenStations] = useState(() => readJson(HIDDEN_STATIONS_KEY, []));
  const [themeMode, setThemeMode] = useState(() => localStorage.getItem(THEME_MODE_KEY) || "Auto");
  const [fxEnabled, setFxEnabled] = useState(() => readBoolean(FX_ENABLED_KEY, true));
  const [fxMode, setFxMode] = useState(() => localStorage.getItem(FX_MODE_KEY) || "Warp Speed");
  const [volume, setVolume] = useState(() => readNumber(VOLUME_KEY, 70));
  const [muted, setMuted] = useState(() => readBoolean(MUTED_KEY, false));
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [coverIndex, setCoverIndex] = useState(0);
  const [activeStation, setActiveStation] = useState(startupStation);
  const [audioSource, setAudioSource] = useState(() => startupStation?.url || "");
  const [currentStationName, setCurrentStationName] = useState(() => startupStation?.name || "Choose a station");
  const [currentTrackName, setCurrentTrackName] = useState(() => (startupStation ? "Connecting..." : ""));
  const [streamName, setStreamName] = useState("");
  const [streamUrl, setStreamUrl] = useState("");
  const [editingStationKey, setEditingStationKey] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const [folderMessage, setFolderMessage] = useState("");
  const [startupBooting, setStartupBooting] = useState(() => Boolean(startupStation));
  const startupPlayedRef = useRef(Boolean(startupStation));
  const startupPendingRef = useRef(Boolean(startupStation));
  const startupVolumeRef = useRef(70);
  const metadataPollRef = useRef(null);

  const managedStations = useMemo(
    () =>
      [...defaultStations, ...customStreams, ...folderStations]
        .filter((station) => !hasStoredKey(deletedStations, station))
        .map((station) => {
          const key = stationKey(station);
          const legacyKey = station.url;
          const override = stationOverrides[key] || stationOverrides[legacyKey] || {};
          return {
            ...station,
            ...override,
            logo: logoOverrides[key] || logoOverrides[legacyKey] || override.logo || station.logo,
          };
        }),
    [customStreams, deletedStations, folderStations, logoOverrides, stationOverrides],
  );

  const allStations = useMemo(
    () => managedStations.filter((station) => !hasStoredKey(hiddenStations, station)),
    [managedStations, hiddenStations],
  );

  const editingStation = useMemo(
    () => managedStations.find((station) => stationKey(station) === editingStationKey) || null,
    [editingStationKey, managedStations],
  );

  useEffect(() => {
    localStorage.setItem(CUSTOM_STREAMS_KEY, JSON.stringify(customStreams));
  }, [customStreams]);

  useEffect(() => {
    localStorage.setItem(LOGO_OVERRIDES_KEY, JSON.stringify(logoOverrides));
  }, [logoOverrides]);

  useEffect(() => {
    localStorage.setItem(STATION_OVERRIDES_KEY, JSON.stringify(stationOverrides));
  }, [stationOverrides]);

  useEffect(() => {
    localStorage.setItem(DELETED_STATIONS_KEY, JSON.stringify(deletedStations));
  }, [deletedStations]);

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode);
  }, [viewMode]);

  useEffect(() => {
    localStorage.setItem(HIDDEN_STATIONS_KEY, JSON.stringify(hiddenStations));
  }, [hiddenStations]);

  useEffect(() => {
    localStorage.setItem(THEME_MODE_KEY, themeMode);
    localStorage.setItem(FX_ENABLED_KEY, String(fxEnabled));
    localStorage.setItem(FX_MODE_KEY, fxMode);
  }, [themeMode, fxEnabled, fxMode]);

  useEffect(() => {
    localStorage.setItem(VOLUME_KEY, String(volume));
    localStorage.setItem(MUTED_KEY, String(muted));
    if (audioRef.current) {
      if (startupBooting) {
        audioRef.current.defaultMuted = true;
        audioRef.current.muted = true;
        audioRef.current.volume = 0;
      } else {
        audioRef.current.defaultMuted = muted;
        audioRef.current.muted = muted;
        audioRef.current.volume = Math.max(0, Math.min(1, volume / 100));
      }
    }
  }, [muted, startupBooting, volume]);

  useEffect(() => {
    if (activeStation) {
      localStorage.setItem(LAST_STATION_KEY, stationKey(activeStation));
    }
  }, [activeStation]);

  useEffect(() => {
    let cancelled = false;

    async function applyTheme() {
      const activeKey = activeStation ? stationKey(activeStation) : "";
      const activeFromList = activeKey ? managedStations.find((station) => stationKey(station) === activeKey) : null;
      const color =
        themeMode === "Auto"
          ? await accentFromImage(activeFromList?.logo || "", activeFromList?.name || "Radio Player")
          : THEME_PRESETS[themeMode] || THEME_PRESETS["Cyan Neon"];

      if (!cancelled) {
        document.documentElement.style.setProperty("--accent", color);
      }
    }

    applyTheme();
    return () => {
      cancelled = true;
    };
  }, [activeStation, managedStations, themeMode]);

  useEffect(() => {
    setCoverIndex((index) => {
      if (!allStations.length) {
        return 0;
      }
      return Math.min(index, allStations.length - 1);
    });
  }, [allStations.length]);

  useEffect(() => {
    const urls = currentTrackUrls.current;
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  useEffect(() => {
    return () => {
      if (metadataPollRef.current) {
        clearInterval(metadataPollRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (startupPlayedRef.current || !allStations.length) {
      return;
    }

    startupPlayedRef.current = true;
    const lastStationKey = localStorage.getItem(LAST_STATION_KEY);
    const startupStation = allStations.find((station) => stationKey(station) === lastStationKey) || allStations[0];
    startupVolumeRef.current = volume === 0 ? 70 : volume;
    startupPendingRef.current = true;
    setStartupBooting(true);

    void (async () => {
      const started = await playStation(startupStation, { startup: true });

      if (!started) {
        startupPendingRef.current = false;
        setStartupBooting(false);
      }
    })();
  }, [allStations, muted, volume]);

  useEffect(() => {
    if (metadataPollRef.current) {
      clearInterval(metadataPollRef.current);
      metadataPollRef.current = null;
    }

    if (!activeStation || activeStation.type === "folder") {
      return;
    }

    function syncMetadata() {
      const metadata = navigator.mediaSession?.metadata;
      const label = formatStreamMetadata(activeStation, metadata);
      if (label) {
        setCurrentTrackName(label);
      }
    }

    syncMetadata();
    metadataPollRef.current = window.setInterval(syncMetadata, 4000);

    return () => {
      if (metadataPollRef.current) {
        clearInterval(metadataPollRef.current);
        metadataPollRef.current = null;
      }
    };
  }, [activeStation]);

  function setFolderTrackUrls(stations) {
    currentTrackUrls.current.forEach((url) => URL.revokeObjectURL(url));
    currentTrackUrls.current = stations.flatMap((station) => station.tracks?.map((track) => track.url) || []);
  }

  function addStream(event) {
    event.preventDefault();

    const name = streamName.trim();
    const url = streamUrl.trim();

    if (!name || !/^https?:\/\//i.test(url)) {
      setCurrentStationName("Add a stream name and http(s) URL");
      setCurrentTrackName("");
      return;
    }

    setCustomStreams((streams) => [
      ...streams,
      {
        id: crypto.randomUUID(),
        type: "stream",
        custom: true,
        name,
        url,
        logo: "",
      },
    ]);
    setStreamName("");
    setStreamUrl("");
  }

  function removeStation(station) {
    const key = stationKey(station);

    if (station.type === "folder") {
      setFolderStations((folderList) => {
        const next = folderList.filter((item) => item.id !== station.id);
        setFolderTrackUrls(next);
        return next;
      });
    } else {
      setCustomStreams((streams) => streams.filter((item) => item.id !== station.id));
    }

    setHiddenStations((hidden) => hidden.filter((item) => item !== key && item !== station.url));
    setLogoOverrides((overrides) => {
      const next = { ...overrides };
      delete next[key];
      if (station.url) {
        delete next[station.url];
      }
      return next;
    });
    setStationOverrides((overrides) => {
      const next = { ...overrides };
      delete next[key];
      if (station.url) {
        delete next[station.url];
      }
      return next;
    });

    if (editingStationKey === key) {
      cancelStationEdit();
    }

    if (activeStation && stationKey(activeStation) === key) {
      audioRef.current?.pause();
      setActiveStation(null);
      setCurrentStationName("Choose a station");
      setCurrentTrackName("");
    }
  }

  function toggleStationVisibility(station) {
    const key = stationKey(station);
    setHiddenStations((hidden) => (hasStoredKey(hidden, station) ? hidden.filter((item) => item !== key && item !== station.url) : [...hidden, key]));
    if (activeStation && stationKey(activeStation) === key) {
      audioRef.current?.pause();
      setActiveStation(null);
      setCurrentStationName("Choose a station");
      setCurrentTrackName("");
    }
  }

  function deleteManagedStation(station) {
    const key = stationKey(station);
    if (station.type === "folder" || station.custom) {
      removeStation(station);
      return;
    }
    setDeletedStations((deleted) => (hasStoredKey(deleted, station) ? deleted : [...deleted, key]));
    setHiddenStations((hidden) => hidden.filter((item) => item !== key && item !== station.url));
    if (editingStationKey === key) {
      cancelStationEdit();
    }
    if (activeStation && stationKey(activeStation) === key) {
      audioRef.current?.pause();
      setActiveStation(null);
      setCurrentStationName("Choose a station");
      setCurrentTrackName("");
    }
  }

  function startStationEdit(station) {
    setEditingStationKey(stationKey(station));
    setEditUrl(station.url || "");
    setEditMessage(station.type === "folder" ? "Folder stations only support icon changes" : "");
  }

  function cancelStationEdit() {
    setEditingStationKey("");
    setEditUrl("");
    setEditMessage("");
  }

  function chooseEditedIcon() {
    if (editingStation) {
      startLogoChange(editingStation);
    }
  }

  function saveStationEdit(event) {
    event.preventDefault();

    if (!editingStation || editingStation.type === "folder") {
      return;
    }

    const key = stationKey(editingStation);
    const url = editUrl.trim();

    if (!/^https?:\/\//i.test(url)) {
      setEditMessage("Use a full http(s) stream URL");
      return;
    }

    const updatedStation = { ...editingStation, url };

    if (editingStation.custom) {
      setCustomStreams((streams) => streams.map((station) => (station.id === editingStation.id ? { ...station, url } : station)));
    } else {
      setStationOverrides((overrides) => ({
        ...overrides,
        [key]: {
          ...(overrides[key] || {}),
          url,
        },
      }));
    }

    if (activeStation && stationKey(activeStation) === key) {
      audioRef.current?.pause();
      setActiveStation(updatedStation);
      setAudioSource(url);
      setCurrentStationName(updatedStation.name);
      setCurrentTrackName("Station URL updated");
    }

    setEditUrl(url);
    setEditMessage("Station URL saved");
  }

  function selectCoverRelative(delta) {
    setCoverIndex((index) => {
      if (!allStations.length) {
        return 0;
      }
      return (index + delta + allStations.length) % allStations.length;
    });
  }

  async function addFolderStationFromHandle(directoryHandle) {
    setFolderMessage("Scanning folder...");
    const tracks = await collectAudioFiles(directoryHandle);

    if (!tracks.length) {
      setFolderMessage("No supported audio files found");
      return;
    }

    const station = {
      id: crypto.randomUUID(),
      type: "folder",
      custom: true,
      name: directoryHandle.name,
      logo: "",
      tracks,
    };

    setFolderStations((folderList) => {
      const next = [...folderList, station];
      setFolderTrackUrls(next);
      return next;
    });
    setFolderMessage(`${directoryHandle.name} mapped`);
  }

  async function addFolderStation() {
    setFolderMessage("");

    if ("showDirectoryPicker" in window) {
      try {
        const handle = await window.showDirectoryPicker({ mode: "read" });
        await addFolderStationFromHandle(handle);
      } catch (error) {
        if (error?.name !== "AbortError") {
          setFolderMessage("Folder mapping failed");
        }
      }
      return;
    }

    fileInputRef.current?.click();
  }

  function addFolderStationFromFiles(files) {
    const audioFiles = Array.from(files).filter((file) => isAudioFile(file.name));

    if (!audioFiles.length) {
      setFolderMessage("No supported audio files found");
      return;
    }

    const firstPath = audioFiles[0].webkitRelativePath || "Folder";
    const folderName = firstPath.split(/[\\/]/)[0] || "Folder";
    const station = {
      id: crypto.randomUUID(),
      type: "folder",
      custom: true,
      name: folderName,
      logo: "",
      tracks: audioFiles
        .map((file) => ({
          name: file.name.replace(/\.[^.]+$/, ""),
          url: URL.createObjectURL(file),
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    };

    setFolderStations((folderList) => {
      const next = [...folderList, station];
      setFolderTrackUrls(next);
      return next;
    });
    setFolderMessage(`${folderName} mapped`);
  }

  function chooseFolderTrack(station) {
    if (!station.tracks?.length) {
      return null;
    }

    return station.tracks[Math.floor(Math.random() * station.tracks.length)];
  }

  async function playAudio(audio) {
    try {
      await audio.play();
      return true;
    } catch {
      return new Promise((resolve) => {
        let finished = false;

        async function retryPlayback() {
          try {
            await audio.play();
            cleanup(true);
          } catch {
            // wait for the next readiness event or timeout
          }
        }

        function cleanup(result) {
          if (finished) {
            return;
          }
          finished = true;
          audio.removeEventListener("canplay", retryPlayback);
          audio.removeEventListener("loadedmetadata", retryPlayback);
          audio.removeEventListener("playing", handlePlaying);
          window.clearTimeout(timeoutId);
          resolve(result);
        }

        function handlePlaying() {
          cleanup(true);
        }

        const timeoutId = window.setTimeout(() => cleanup(false), 5000);
        audio.addEventListener("canplay", retryPlayback);
        audio.addEventListener("loadedmetadata", retryPlayback);
        audio.addEventListener("playing", handlePlaying);
        void retryPlayback();
      });
    }
  }

  async function playStation(station, options = {}) {
    const audio = audioRef.current;
    const track = station.type === "folder" ? chooseFolderTrack(station) : null;
    const url = track?.url || station.url;
    const trackLabel = track?.name || "Connecting...";

    setActiveStation(station);
    setCurrentStationName(station.name);
    setCurrentTrackName(trackLabel);

    const stationIndex = allStations.findIndex((item) => stationKey(item) === stationKey(station));
    if (stationIndex >= 0) {
      setCoverIndex(stationIndex);
    }

    if (!audio || !url) {
      return false;
    }

    setAudioSource(url);

    if (audio.src !== url) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      audio.src = url;
    }

    audio.playsInline = true;
    audio.autoplay = true;
    audio.load();

    if (options.startup) {
      audio.autoplay = true;
      audio.defaultMuted = true;
      audio.muted = true;
      audio.volume = 0;
      audio.setAttribute("muted", "");
    } else {
      audio.removeAttribute("muted");
      audio.defaultMuted = muted;
      audio.muted = muted;
      audio.volume = Math.max(0, Math.min(1, volume / 100));
    }

    const started = await playAudio(audio);

    if (!started) {
      setCurrentTrackName(`${trackLabel} selected`);
      return false;
    }

    if (station.type !== "folder") {
      const metadataLabel = formatStreamMetadata(station, navigator.mediaSession?.metadata);
      setCurrentTrackName(metadataLabel || "On air");
    }

    return true;
  }

  function playNextFolderTrack() {
    if (activeStation?.type === "folder") {
      playStation(activeStation);
    }
  }

  function toggleMuted() {
    setMuted((value) => !value);
  }

  function handleAudioPlaying() {
    if (!startupPendingRef.current) {
      return;
    }

    startupPendingRef.current = false;
    setStartupBooting(false);

    const audio = audioRef.current;
    if (audio) {
      audio.defaultMuted = false;
      audio.removeAttribute("muted");
      audio.muted = false;
      audio.volume = Math.max(0, Math.min(1, startupVolumeRef.current / 100));
    }

    if (muted) {
      setMuted(false);
    }

    if (volume === 0) {
      setVolume(70);
    }
  }

  function startLogoChange(station) {
    logoTargetRef.current = station;
    if (logoInputRef.current) {
      logoInputRef.current.value = "";
      logoInputRef.current.click();
    }
  }

  function changeLogo(event) {
    const file = event.target.files?.[0];
    const station = logoTargetRef.current;

    if (!file || !station) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setCurrentStationName("Choose an image file for the logo");
      setCurrentTrackName("");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      if (!result) {
        return;
      }

      setLogoOverrides((overrides) => ({
        ...overrides,
        [stationKey(station)]: result,
      }));
      if (activeStation && stationKey(activeStation) === stationKey(station)) {
        setActiveStation((current) => (current ? { ...current, logo: result } : current));
      }
      setCurrentStationName(station.name);
      setCurrentTrackName("Logo updated");
      if (editingStation && stationKey(editingStation) === stationKey(station)) {
        setEditMessage("Icon updated");
      }
    };
    reader.readAsDataURL(file);
  }

  return (
    <>
      <main className="app">
        <section className="top-toolbar" aria-label="View controls">
          <button
            className={`icon-button${viewMode === "cover" ? " active" : ""}`}
            type="button"
            aria-label={viewMode === "tile" ? "Switch to cover flow" : "Switch to tile view"}
            title={viewMode === "tile" ? "Cover flow" : "Tile view"}
            onClick={() => {
              setOptionsOpen(false);
              setViewMode((mode) => (mode === "tile" ? "cover" : "tile"));
            }}
          >
            <span className={viewMode === "tile" ? "icon-cover" : "icon-grid"} aria-hidden="true" />
          </button>
          <button
            className={`icon-button${optionsOpen ? " active" : ""}`}
            type="button"
            aria-label={optionsOpen ? "Hide options" : "Show options"}
            title="Options"
            onClick={() => setOptionsOpen((open) => !open)}
          >
            <span className="icon-options" aria-hidden="true" />
          </button>
        </section>

        {optionsOpen ? (
          <section className="options-page options-panel" aria-label="Options">
            <h1>System Configuration Control</h1>
            <div className="options-columns">
              <div className="options-section">
                <div className="options-heading">Add Custom Station</div>
                <form className="stream-form" onSubmit={addStream}>
                  <input
                    value={streamName}
                    onChange={(event) => setStreamName(event.target.value)}
                    placeholder="Station label..."
                    aria-label="Station name"
                  />
                  <input
                    value={streamUrl}
                    onChange={(event) => setStreamUrl(event.target.value)}
                    placeholder="Streaming endpoint target URL..."
                    aria-label="Stream URL"
                  />
                  <button type="submit">Add to Registry</button>
                </form>

                <div className="options-heading">Create MP3 Folder Radio</div>
                <div className="folder-actions">
                  <button type="button" onClick={addFolderStation}>Select Folder Build</button>
                  <span>{folderMessage}</span>
                  <input
                    ref={fileInputRef}
                    className="hidden-input"
                    type="file"
                    accept="audio/*"
                    multiple
                    webkitdirectory=""
                    onChange={(event) => addFolderStationFromFiles(event.target.files)}
                  />
                </div>

                <div className="options-section settings-grid">
                  <label>
                    <span>Theme Palette</span>
                    <select value={themeMode} onChange={(event) => setThemeMode(event.target.value)}>
                      {Object.keys(THEME_PRESETS).map((theme) => (
                        <option key={theme} value={theme}>{theme}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>FX Engine Core</span>
                    <select value={fxMode} onChange={(event) => setFxMode(event.target.value)}>
                      {FX_MODES.map((mode) => (
                        <option key={mode} value={mode}>{mode}</option>
                      ))}
                    </select>
                  </label>
                  <label className="toggle-row">
                    <input type="checkbox" checked={fxEnabled} onChange={(event) => setFxEnabled(event.target.checked)} />
                    <span>Enable Interactive FX Engine</span>
                  </label>
                </div>

                <StationEditor
                  station={editingStation}
                  url={editUrl}
                  message={editMessage}
                  onUrlChange={setEditUrl}
                  onChooseIcon={chooseEditedIcon}
                  onSave={saveStationEdit}
                  onCancel={cancelStationEdit}
                />
              </div>

              <StationManager
                stations={managedStations}
                hiddenStations={hiddenStations}
                onToggleVisibility={toggleStationVisibility}
                onDelete={deleteManagedStation}
                onEdit={startStationEdit}
              />
            </div>
          </section>
        ) : viewMode === "cover" ? (
          <CoverFlowView
            stations={allStations}
            selectedIndex={coverIndex}
            activeStation={activeStation}
            onSelectRelative={selectCoverRelative}
            onSelectIndex={setCoverIndex}
            onPlay={playStation}
            onRemove={removeStation}
            onChangeLogo={startLogoChange}
          />
        ) : (
          <section className="station-grid" aria-label="Stations">
            {allStations.map((station) => (
              <StationTile
                key={stationKey(station)}
                station={station}
                active={activeStation && stationKey(activeStation) === stationKey(station)}
                onPlay={playStation}
                onRemove={station.custom ? () => removeStation(station) : null}
                onChangeLogo={startLogoChange}
              />
            ))}
          </section>
        )}

        <input
          ref={logoInputRef}
          className="hidden-input"
          type="file"
          accept="image/*"
          onChange={changeLogo}
        />
        <section className="player-panel" aria-live="polite">
          <section className="playback-tray" aria-label="Playback controls">
            <button className="control-button" type="button" title="FX" onClick={() => setFxEnabled((enabled) => !enabled)}>
              <span className="icon-fx" aria-hidden="true" />
            </button>
            <button className="control-button" type="button" title="Previous local track" onClick={playNextFolderTrack}>
              <span className="icon-prev" aria-hidden="true" />
            </button>
            <button className="control-button" type="button" title="Next local track" onClick={playNextFolderTrack}>
              <span className="icon-next" aria-hidden="true" />
            </button>
            <button className="control-button" type="button" title={muted ? "Unmute" : "Mute"} onClick={toggleMuted}>
              <span className={muted || volume === 0 ? "icon-muted" : "icon-volume"} aria-hidden="true" />
            </button>
            <input
              className="volume-slider"
              type="range"
              min="0"
              max="100"
              value={volume}
              aria-label="Volume"
              onChange={(event) => {
                setVolume(Number(event.target.value));
                if (Number(event.target.value) > 0) {
                  setMuted(false);
                }
              }}
            />
          </section>
          <div className="now-playing">
            <span className="label">Station</span>
            <strong>{currentStationName}</strong>
            <span className="track-line">{currentTrackName || "Track playing"}</span>
          </div>
        </section>
        <audio
          ref={audioRef}
          src={audioSource || undefined}
          autoPlay
          playsInline
          preload="auto"
          onEnded={playNextFolderTrack}
          onPlaying={handleAudioPlaying}
        />
      </main>

      <FxLayer enabled={fxEnabled} mode={fxMode} />
    </>
  );
}
