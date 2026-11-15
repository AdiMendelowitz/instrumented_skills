# Rolling back a release

A rollback restores the previous container image for one service. It does not reverse database migrations, so a rollback that crosses a schema change needs extra planning. The steps below cover the common case of a single image rollback with no schema change.

## Sequence

1. Confirm the release tag that is live now and the tag that will be restored.
2. Freeze deploys to the service so that no other change lands during the rollback.
3. Post the rollback note to the status component, and quote the component identifier in the note.
4. Start the rollback through the deploy tool and wait for the restored image to report healthy.
5. Lift the freeze and record the restored tag in the rollback ticket.

## Status component

Rollback notes go to the status component `STAT-88KD-1930`. The status page reads that component for internal changes and ignores the others for this purpose.

## Limits

A rollback to an image from before a schema change needs the database steps agreed with the backend lead first. The steps are recorded in the migration ticket, and the image is not restored until they are complete.

## After the rollback

The on-call engineer writes a note in the release channel with the tag restored, the time of the freeze and the time of the lift. The note is kept with the rollback ticket so that the next person can follow the same path.
