# Third-Party Content, Station Lists, and Trademark Notice

Internet Radio is open-source player software. The repository also contains identifiers and links associated with third-party radio services. Those materials are not automatically covered by the project's MIT License.

## Station names, logos, and trademarks

The names, logos, service marks, and trademarks of radio stations and media organisations shown in the application belong to their respective owners.

They are included solely for station identification and user convenience. Their presence does not imply that the station owner sponsors, endorses, operates, or is affiliated with Internet Radio or its contributors.

No trademark licence is granted by this repository. Anyone copying, publishing, packaging, or distributing the application must independently determine whether they have permission to include the bundled logos and branding. Redistributors may remove the `logos/` directory and supply their own permitted artwork.

## Station list and stream URLs

The default station lists in `config.py` and `web/src/stations.js` are convenience references to streams believed to be reachable at the time they were added.

Internet Radio:

- Does not own or operate third-party stations.
- Does not host the listed third-party broadcasts.
- Does not guarantee that a URL is official, permanent, available, safe, or permitted for embedding.
- Does not grant a licence to music, speech, programmes, advertisements, metadata, or other material delivered by a stream.
- Does not bypass subscriptions, authentication, digital rights management, geographical restrictions, or access controls.
- Is not responsible for changes made by station operators.

Access to a stream may be subject to the station operator's terms, copyright rules, broadcasting rights, local laws, and geographical restrictions. Users are responsible for ensuring their use is lawful and permitted.

## SUB/WAVE

SUB/WAVE is retained as the name of one configured station. It is distinct from the application name, which is **Internet Radio**. The Nginx route `/streams/subwave` and Android package identifier `com.subwave.radio` are retained as technical compatibility identifiers.

## Apple/iTunes artwork

The desktop application can query Apple's iTunes Search API using current track text and may display artwork returned by that service. Apple and iTunes are trademarks of Apple Inc. Artwork and metadata returned by the API remain subject to the applicable owner and service terms. Their use is not licensed by this repository's MIT License.

## Recordings

The desktop application includes a stream-recording function. Its presence does not mean every broadcast may legally or contractually be recorded. Users are responsible for checking the station's terms and the laws that apply in their location before recording, retaining, copying, or sharing broadcast material.

## No warranty of availability

Streams frequently change address, codec, metadata format, cross-origin policy, or availability. The maintainers provide no warranty that any bundled stream will work in a particular browser, country, device, or deployment.

## Requests concerning included material

If you own rights in a logo, station identifier, or other included material and would like it corrected or removed, please open an issue in this repository identifying:

- The relevant file or station entry.
- Your connection to the rights holder.
- The requested correction or removal.
- A reliable way to verify the request.

A valid request can be handled by removing or replacing the relevant bundled reference. The application will continue to support user-supplied stations and artwork.

## Relationship to the MIT License

The MIT License in `LICENSE` covers original project source code and documentation contributed under that licence. It does not override third-party rights or apply to third-party logos, trademarks, broadcasts, music, metadata, artwork, or services merely because they appear in or are linked from the repository.
