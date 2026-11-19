import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { safetyApi } from '@/api/safety'
import { AppShell } from '@/components/AppShell'
import { RevealGroup } from '@/components/motion/RevealGroup'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import type { BlockedUserOut } from '@/api/types'
import { PageBanner } from '@/components/PageBanner'

/** PRD §10: blocking "cannot be undone by the blocked party" — which implies
 * the blocker can. Nothing in the PRD's §9 screen table specs this page;
 * it exists because the backend already supported unblocking (D-7.5) with
 * no way to reach it — once blocked, a match's detail page 403s, so there
 * was no route back for a mistaken block (found live, after Phase 7 shipped). */
export function BlockedUsers() {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['blocks'],
    queryFn: () => safetyApi.listBlocks(),
  })

  const unblockMutation = useMutation({
    mutationFn: (blockedId: string) => safetyApi.unblock(blockedId),
    onSuccess: (_data, blockedId) => {
      queryClient.setQueryData<BlockedUserOut[]>(['blocks'], (prev) =>
        prev?.filter((u) => u.id !== blockedId),
      )
      // The unblocked person becomes eligible again — don't leave a stale
      // match list around either (same lesson as BlockConfirmDialog.tsx).
      queryClient.invalidateQueries({ queryKey: ['matches'] })
    },
  })

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-7">
        <PageBanner photo="/photos/keys.webp" title="Blocked" size="sm" className="mb-5">
          <p className="text-[13px] leading-[1.4] text-white/85">
            Unblocking someone lets you match with each other again. They're never notified either way.
          </p>
        </PageBanner>

        {isLoading && <p className="text-cohab-muted">Loading…</p>}
        {error && <p className="text-cohab-accent">Couldn't load your blocked users.</p>}
        {data && data.length === 0 && <p className="text-cohab-muted">You haven't blocked anyone.</p>}

        <RevealGroup className="flex flex-col gap-2" runKey={data?.length}>
          {data?.map((u) => (
            <div
              key={u.id}
              className="flex items-center gap-3 surface rounded-[22px] p-4"
            >
              <Avatar name={u.full_name} src={u.avatar_url} size={44} />
              <span className="flex-1 text-[14.5px] font-medium text-cohab-ink truncate">{u.full_name}</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => unblockMutation.mutate(u.id)}
                disabled={unblockMutation.isPending}
              >
                Unblock
              </Button>
            </div>
          ))}
        </RevealGroup>
      </div>
    </AppShell>
  )
}
