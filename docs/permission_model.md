
# resources

- namespace (permission-controlled)
- repository (permission-controlled)
- app/version (controlled via repository permissions)


# repository permissions

- READ: view app spec, jenkins, download docker
- WRITE: upload, trigger etc... (no upload of docker)
- READ_ACP: read permissions
- WRITE_ACP: change permissions (prevent deletion of owner permission?)
- FULL_CONTROL: everything including deletion of repo

# namespace permissions

- READ: read perm on all repos if NOT AllUsers  (listing supports only repos with read access)
- WRITE: write perm on all repos (if user creates new repo, user gets FULL_CONTROL)
- READ_ACP: read permissions on namespace and all repos
- WRITE_ACP: change permissions on namespace all repos
- FULL_CONTROL: implies FULL_CONTROL on all repos