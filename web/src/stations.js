const logoUrl = (fileName) => new URL(`../../logos/${fileName}`, import.meta.url).href;
const subwaveStreamUrl = import.meta.env.VITE_SUBWAVE_STREAM_URL || "/streams/subwave";

export const stations = [
  {
    name: "Dance Radio UK",
    url: "https://dancestream.danceradiouk.com/stream",
    logo: logoUrl("dance_radio_uk.png"),
  },
  {
    name: "SUB/WAVE",
    url: subwaveStreamUrl,
    logo: logoUrl("subwave.png"),
  },
  {
    name: "Capital Dance UK",
    url: "http://icecast.thisisdax.com/CapitalDanceMP3",
    logo: logoUrl("capital_dance_uk.png"),
  },
  {
    name: "Heart Dance",
    url: "http://icecast.thisisdax.com/HeartDanceMP3",
    logo: logoUrl("heart_dance.png"),
  },
  {
    name: "GB News Radio",
    url: "https://listen-gbnews.sharp-stream.com/gbnews.mp3",
    logo: logoUrl("gb_news_radio.png"),
  },
  {
    name: "Smooth Radio",
    url: "https://icecast.thisisdax.com/SmoothUKMP3",
    logo: logoUrl("smooth_radio.png"),
  },
  {
    name: "Heart UK",
    url: "https://icecast.thisisdax.com/HeartUKMP3",
    logo: logoUrl("heart_uk.png"),
  },
  {
    name: "Radio X UK",
    url: "https://icecast.thisisdax.com/RadioXUKMP3",
    logo: logoUrl("radio_x_uk.png"),
  },
  {
    name: "Radio Paradise",
    url: "https://stream.radioparadise.com/rock-192",
    logo: logoUrl("radio_paradise.png"),
  },
  {
    name: "Soma",
    url: "https://ice1.somafm.com/indiepop-128-mp3",
    logo: logoUrl("soma.png"),
  },
  {
    name: "Bassdrive",
    url: "http://stream.bassdrive.com:8000/;stream.mp3",
    logo: logoUrl("bassdrive.png"),
  },
  {
    name: "Virgin Hard Rock",
    url: "http://icy.unitedradio.it/VirginHardRock.mp3",
    logo: logoUrl("virgin_hard_rock.png"),
  },
  {
    name: "The Rock",
    url: "https://mediaworks.streamguys1.com/rock_net_icy",
    logo: logoUrl("the_rock.png"),
  },
];
