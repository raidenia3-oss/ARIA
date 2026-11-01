\ = 'C:\Users\User\Downloads\AURA\v5\src\App.tsx'
\ = [System.IO.File]::ReadAllText(\)
\ = '<div className=""pointer-events-none absolute inset-0 bg-gradient-to-br from-bg-dark-0 via-bg-dark-1 to-bg-dark-2 opacity-80"" />'
\ = '<div className=""aurora pointer-events-none absolute inset-0"" /><div className=""mesh-ambient pointer-events-none absolute inset-0"" />'
if (\ -like '*bg-gradient-to-br*') {
  \ = \ -replace '<div className=""pointer-events-none absolute inset-0 bg-gradient-to-br from-bg-dark-0 via-bg-dark-1 to-bg-dark-2 opacity-80"" />', \
  [System.IO.File]::WriteAllText(\, \)
  'ok'
} else { 'no' }
