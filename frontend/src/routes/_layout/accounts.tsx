import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { AccountsService } from "@/client"
import AddAccount from "@/components/Accounts/AddAccount"
import { columns } from "@/components/Accounts/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingAccounts from "@/components/Pending/PendingAccounts"

function getAccountsQueryOptions() {
  return {
    queryFn: () => AccountsService.readAccounts({ skip: 0, limit: 100 }),
    queryKey: ["accounts"],
  }
}

export const Route = createFileRoute("/_layout/accounts")({
  component: Accounts,
  head: () => ({
    meta: [{ title: "Accounts - AutoTrade" }],
  }),
})

function AccountsTableContent() {
  const { data: accounts } = useSuspenseQuery(getAccountsQueryOptions())

  return <DataTable columns={columns} data={accounts.data} />
}

function AccountsTable() {
  return (
    <Suspense fallback={<PendingAccounts />}>
      <AccountsTableContent />
    </Suspense>
  )
}

function Accounts() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Exchange Accounts
          </h1>
          <p className="text-muted-foreground">
            Manage your connected exchange API accounts
          </p>
        </div>
        <AddAccount />
      </div>
      <AccountsTable />
    </div>
  )
}
