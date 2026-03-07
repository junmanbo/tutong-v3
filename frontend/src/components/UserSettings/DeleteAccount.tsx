import DeleteConfirmation from "./DeleteConfirmation"

const DeleteAccount = () => {
  return (
    <div className="max-w-md mt-4 rounded-lg border border-destructive/50 p-4">
      <h3 className="font-semibold text-destructive">계정 삭제</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        계정과 모든 관련 데이터를 영구적으로 삭제합니다.
      </p>
      <DeleteConfirmation />
    </div>
  )
}

export default DeleteAccount
