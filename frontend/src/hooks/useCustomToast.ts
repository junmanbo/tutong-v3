import { toast } from "sonner"

const useCustomToast = () => {
  const showSuccessToast = (description: string) => {
    toast.success("완료", {
      description,
    })
  }

  const showErrorToast = (description: string) => {
    toast.error("오류가 발생했습니다", {
      description,
    })
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
